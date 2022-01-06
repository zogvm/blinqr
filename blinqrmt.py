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

#========================send==========start========================

isEnd=False
def set_block(stream,block_size,q_block):
    global isEnd   
    i=0     
    start_time = time.time()
    for block in encode.encoder(stream, block_size):  # max size is 2350
        q_block.put(block,True)
        #time.sleep(0.001)	
        if isEnd:
            break

        if isDebug:
            end_time = time.time()
            i+=1
            print("block time:{:.2f},{:d}".format(end_time-start_time,i))
            start_time = time.time()
        
    isEnd=True

def set_img(index,q_block,q_img):
    global isEnd   
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
            time.sleep(0.001)	
            if isEnd:
                break
        
def send(data: bytes, *, block_size: int = 2350):
    assert block_size <= 2350

    global isEnd  
    sha1 = calculate_sha1(data)
    stream = BytesIO(data)
    print(colored(f'多进程模式{len(data)} bytes, SHA-1: {sha1}', 'blue'))
    
    root = Tk()
    screen_h= root.winfo_screenheight()
    screen_w= root.winfo_screenwidth()
    #计算是否显示2个二维码
    if screen_h> screen_w:
        if screen_h/screen_w >16.0/10.1:
            win_s=screen_w-80
            is_two=True
            if win_s>screen_h/2:
                win_s=screen_h/2
        else:
            win_s=screen_w-80
            is_two=False
    else:
        if screen_w/screen_h >16.0/10.1:
            win_s=screen_h-80
            is_two=True
            if win_s>screen_w/2:
                win_s=screen_w/2
        else:
            win_s=screen_h-80
            is_two=False

    win_s=win_s-10

    print("w:{:f},h:{:f},win:{:f},two:{:d}".format(screen_w,screen_h,win_s,is_two))

    cv2.namedWindow('sender1', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('sender1',int(win_s),int(win_s))
    cv2.moveWindow('sender1',0,0)

    if is_two:
        cv2.namedWindow('sender2', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('sender2',int(win_s),int(win_s)) 
        cv2.moveWindow('sender2',int(win_s)+10,0)

    start_time = time.time()
    i=0     
    q_block = multiprocessing.Queue(30)
    q_img = multiprocessing.Queue(30)
    t1 = multiprocessing.Process(target=set_block,args=[stream,block_size,q_block])
    t1.start()
    #设为5差不多为15FPS
    for x in range(3):
        t2 = multiprocessing.Process(target=set_img,args=[x,q_block,q_img])
        t2.start()
    
    while True:
        if isEnd and q_block.qsize()==0 and q_img.qsize()==0:
            print("send end")
            break
        if q_img.qsize()>0:	
            i+=1
            print("time:{:.2f},{:d}".format(time.time()-start_time,i))
            img=q_img.get()
            cv2.imshow('sender1', img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
               break
        if is_two:
            if q_img.qsize()>0:	
                i+=1
                print("time:{:.2f},{:d}".format(time.time()-start_time,i))
                img2=q_img.get()
                cv2.imshow('sender2', img2)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        #限成5FPS 
        #不要太快 会糊
        time.sleep(0.2)	
           
    cv2.destroyAllWindows()  
    isEnd=True

 #====================send=========end=================   

 #====================receive======start================    
def read_cap(path,q_img):
    global isEnd 
    i=0
    start_time = time.time()

    if not path:
        cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(path)
    #这里path也可以填rtsp

    w=cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    h=cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print("w:{:f},h:{:f}".format(w,h))

    while True:
        ret, img = cap.read()
        if not ret:
           break
        q_img.put(img,True)
        #time.sleep(0.03)  #33fps for realtime 
        time.sleep(0.001)
        if isEnd:
            break

        i+=1
        print("f time:{:.2f},{:d}".format(time.time()-start_time,i))
       

    cap.release()       
    isEnd=True

def decoded_img(index,q_img,q_decode):
    global isEnd 
    while True:
        if isEnd:
            break  
        time.sleep(0.001)	
        if q_img.qsize()>0:	

            if isDebug:
                start_time = time.time()

            img=q_img.get()
            decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
            
            #灰色    
            if not decoded_qrs:
                img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
                
            #锐化
            if False:
                if not decoded_qrs:
                    img_src=img
                    k= np.array([[0,-1,0],[-1,5,-1],[0,-1,0]])
                    img=cv2.filter2D(img_src,-1,k)
                    decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
                    
            #gamma校准
            if False:
                img_src=img	
                thre = 1.1
                while (len(decoded_qrs) == 0 and thre < 1.8):
                    img = 255*np.power(img_src/255,thre)
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
                
                    
            #二值化 只开这个效果好
            if True:
                img_src=img
                thre = 70
                while (len(decoded_qrs) == 0 and thre < 170):
                    ret2, img = cv2.threshold(img_src, thre, 255, cv2.THRESH_BINARY)
                    decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))
                    thre = thre + 10
                img=img_src
            
            if decoded_qrs:
                for decoded_qr in decoded_qrs:
                    q_decode.put(decoded_qr,True)
                    
            if isDebug:
                print("index={:d},decode time:{:.2f}".format(index,time.time()-start_time))

      
            

           
def read_decode(index,q_decode,q_block):
    global isEnd 
    while True:
        if isEnd:
            break   
        time.sleep(0.001)	
        if q_decode.qsize()>0:	
            if isDebug:
                start_time = time.time()

            decoded_qr=q_decode.get()

            data_decoded = b85decode(decoded_qr.data)
            block = decode.block_from_bytes(data_decoded)
            q_block.put(block,True)

            if isDebug:
                print("index={:d},block time:{:.2f}".format(index,time.time()-start_time))

     

def receive(path):
    global isEnd       
    ltDecoder = decode.LtDecoder()
    empty = True

    q_img = multiprocessing.Queue(30)
    q_decode = multiprocessing.Queue(30)
    q_block = multiprocessing.Queue(30)
    t1 = multiprocessing.Process(target=read_cap,args=[path,q_img])
    t1.start()
    #
    for x in range(5):
        t2 = multiprocessing.Process(target=decoded_img,args=[x,q_img,q_decode])
        t2.start()

    for x in range(1):
        t3 = multiprocessing.Process(target=read_decode,args=[x,q_decode,q_block])
        t3.start()

    start_time = time.time()
    try:
        while True:
            if isEnd and q_decode.qsize()==0 and q_block.qsize()==0 and q_img.qsize()==0:
                print("receive end")
                break
            if q_block.qsize()>0:	
                block=q_block.get()
                ltDecoder.consume_block(block)
                empty = False

                if ltDecoder.is_done():
                    data = ltDecoder.bytes_dump()
                    sha1 = calculate_sha1(data)

                    time_elapsed = time.time() - start_time
                    transfer_speed = len(data) / time_elapsed
                    print(colored(f'done:{len(data)} bytes, SHA-1: {sha1}', 'green'))
                    print(colored(f'done:{time_elapsed:.2f} seconds, {transfer_speed:.2f} B/s', 'green'))
                 
                    with open(path+".out", 'wb') as fw:
                        data = fw.write(data)
                    break

                    ltDecoder = decode.LtDecoder()
                    empty = True
            else:
                time.sleep(0.001)
    finally:
        cv2.destroyAllWindows()
 
    isEnd=True

 #====================receive======end================    