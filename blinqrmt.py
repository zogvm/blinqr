import sys
import cv2
import time
import struct
import numpy as np
from io import BytesIO
from tkinter import Tk
from hashlib import sha1
from segno import make_qr
from pyzbar import pyzbar
from threading import Thread
from termcolor import colored
from lt import encode, decode
from base64 import b85encode, b85decode
from tkinter.filedialog import askopenfilename

import multiprocessing

isDebug=False

def fix_scaling():
    import sys
    if sys.platform == 'win32':
        try:
            import ctypes
            PROCESS_SYSTEM_DPI_AWARE = 1
            ctypes.OleDLL('shcore').SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)
        except (ImportError, AttributeError, OSError):
            pass


def select_file():
    root = Tk()
    root.withdraw()
    path = askopenfilename()
    root.destroy()
    return path


def calculate_sha1(data: bytes) -> str:
    m = sha1()
    m.update(data)
    return m.hexdigest()

def set_block(stream,block_size,q_block):
    i=0     
    start_time = time.time()
    for block in encode.encoder(stream, block_size):  # max size is 2350
        q_block.put(block,True)
        #time.sleep(0.01)	
        
        if isDebug:
            end_time = time.time()
            i+=1
            print("block time:{:.2f},{:d}".format(end_time-start_time,i))
            start_time = time.time()
 
def set_img(index,q_block,q_img):
    while True:
        if q_block.qsize()>0:	
            if isDebug:	
                start_time = time.time()	
            #make_qr最耗 差不多0.2S
            block=q_block.get()
            block_encoded = b85encode(block)
            #2350 l  max size is 2350
            #1024 m
            #512  h
            qr = make_qr(block_encoded, error='l') #177*177
            img = ~np.array(qr.matrix, dtype=np.bool)
            img = np.uint8(img) * 0xFF
            img = np.pad(img, pad_width=20,mode='constant', constant_values=0xFF)
            q_img.put(img,True)
        
            if isDebug:
                end_time = time.time()
                print("index={:d},img time:{:.2f}".format(index,end_time-start_time))
           
        else:
            time.sleep(0.01)	
        


def send(data: bytes, *, block_size: int = 2350):
    #assert block_size <= 2350

    sha1 = calculate_sha1(data)
    stream = BytesIO(data)
    print(colored(f'多进程模式{len(data)} bytes, SHA-1: {sha1}', 'blue'))
    
    root = Tk()
    screen_h= root.winfo_screenheight()
    screen_w= root.winfo_screenwidth()
    print("w:{:f},h:{:f}".format(screen_w,screen_h))
    
    if screen_h> screen_w:
        win_s=screen_w	
    else:
        win_s=screen_h	
    win_s=win_s-80
     
    cv2.namedWindow('sender', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('sender',win_s,win_s)
    
    start_time = time.time()
    i=0     
    q_block = multiprocessing.Queue(30)
    q_img = multiprocessing.Queue(30)
    t1 = multiprocessing.Process(target=set_block,args=[stream,block_size,q_block])
    t1.start()
    #设为5差不多为15FPS
    #不要太快 会糊
    for x in range(3):
        t2 = multiprocessing.Process(target=set_img,args=[x,q_block,q_img])
        t2.start()
    
    while True:
        if q_img.qsize()>0:	
            i+=1
            print("time:{:.2f},{:d}".format(time.time()-start_time,i))
            img=q_img.get()
            cv2.imshow('sender', img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
               break
        #限成10FPS
        time.sleep(0.1)	
           
    cv2.destroyAllWindows()   
    
        

def receive(path):
    qrDecoder = cv2.QRCodeDetector()
    ltDecoder = decode.LtDecoder()
    empty = True
    i=0
    j=0
    if not path:
        cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(path)
        
    w=cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h=cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print("w:{:f},h:{:f}".format(w,h))
    
    try:
        while True:
            ret, img = cap.read()
            if not ret:
                break
                
            #time.sleep(1)    
            
            start_f_time = time.time()
            if empty:
                start_time = time.time()
            
            decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
           
            #灰色    
            if not decoded_qrs:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
            
            #锐化
            if True:
                if not decoded_qrs:
                    img_src=img
                    k= np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
                    img=cv2.filter2D(img_src,-1,k)
                    decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
                
            #gamma校准
            if True:
                img_src=img	
                thre = 1.1
                while (len(decoded_qrs) == 0 and thre < 1.9):
                    img = 255*np.power(img_src/255,1.5)
                    img = np.around(img)
                    img[img>255] = 255
                    img = img.astype(np.uint8)
                    decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
                    thre=thre+0.1
                img=img_src
                
            
            #缩小后边缘扩大
            if False:
                rate=0.9
                if not decoded_qrs:
                    img=cv2.resize(img,None,fx=rate,fy=rate,interpolation=cv2.INTER_LINEAR)	 
                    new_w=int(w-w*rate)
                    new_h=int(h-h*rate)
                    img = cv2.copyMakeBorder(img,new_h,new_h,new_w,new_w, cv2.BORDER_CONSTANT,value=0xFF)
                    decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
            

                
            #二值化
            if True:
                img_src=img
                thre = 70
                while (len(decoded_qrs) == 0 and thre < 180):
                    ret2, img = cv2.threshold(img_src, thre, 255, cv2.THRESH_BINARY)
                    decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
                    thre = thre + 10
                img=img_src
                
            if decoded_qrs:
                step_qrs_time = time.time()
                for decoded_qr in decoded_qrs:
                    polygon = tuple(decoded_qr.polygon)
                    for p1, p2 in zip(polygon, (*polygon[1:], polygon[0])):
                        cv2.line(img, (p1.x, p1.y), (p2.x, p2.y), (255, 0, 0), 3)

                    data_encoded = decoded_qr.data
                    data_decoded = b85decode(data_encoded)

                    block = decode.block_from_bytes(data_decoded)
                    ltDecoder.consume_block(block)
                    empty = False
                    
                    if ltDecoder.is_done():
                        data = ltDecoder.bytes_dump()
                        end_time = time.time()
                        sha1 = calculate_sha1(data)
                        time_elapsed = end_time - start_time
                        transfer_speed = len(data) / time_elapsed

                        print(colored(f'done:{len(data)} bytes, SHA-1: {sha1}', 'green'))
                        print(colored(f'done:{time_elapsed:.2f} seconds, {transfer_speed:.2f} B/s', 'green'))
                        time.sleep(3)
                        
                        with open(path+".out", 'wb') as fw:
                            data = fw.write(data)
                        exit(0)

                        ltDecoder = decode.LtDecoder()
                        empty = True

                    else:
                        j+=1
                        print("qrs time:{:.2f},{:d}".format(time.time()-step_qrs_time,j))
            else:
                i+=1
                print("f time:{:.2f},{:d}".format(time.time()-start_f_time,i))

            cv2.imshow('receiver', img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
