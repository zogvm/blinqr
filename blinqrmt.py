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
 
img_i=0     
def set_img(index,q_block,q_img):
    global img_i
    while True:
        if q_block.qsize()>0:	
            if isDebug:	
                start_time = time.time()	
            #make_qr最耗 差不多0.2S
            block=q_block.get()
            block_encoded = b85encode(block)
            qr = make_qr(block_encoded, error='l')
            img = ~np.array(qr.matrix, dtype=np.bool)
            img = np.uint8(img) * 0xFF
            img = np.pad(img, pad_width=6, mode='constant', constant_values=0xFF)
            q_img.put(img,True)
        
            if isDebug:
                end_time = time.time()
                img_i=img_i+1
                print("index={:d},img time:{:.2f},{:d}".format(index,end_time-start_time,img_i))
           
        else:
            time.sleep(0.01)	
        


def send(data: bytes, *, block_size: int = 2350):
    assert block_size <= 2350

    sha1 = calculate_sha1(data)
    stream = BytesIO(data)
    print(colored(f'多进程模式{len(data)} bytes, SHA-1: {sha1}', 'blue'))

    cv2.namedWindow('sender', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('sender', 960, 960)
    
    start_time = time.time()
    i=0     
    q_block = multiprocessing.Queue(30)
    q_img = multiprocessing.Queue(30)
    t1 = multiprocessing.Process(target=set_block,args=[stream,block_size,q_block])
    t1.start()
    #设为5差不多为15FPS
    for x in range(5):
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
        else:
            time.sleep(0.05)	
           
    cv2.destroyAllWindows()   
    
        

def receive(path):
    qrDecoder = cv2.QRCodeDetector()
    ltDecoder = decode.LtDecoder()
    empty = True
	
    if not path:
        cap = cv2.VideoCapture(0)
    else:
        cap = cv2.VideoCapture(path)
    try:
        while True:
            _, img = cap.read()

            if empty:
                start_time = time.time()

            decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))

            if decoded_qrs:
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

                        print(colored(f'{len(data)} bytes, SHA-1: {sha1}', 'green'))
                        print(colored(f'{time_elapsed:.2f} seconds, {transfer_speed:.2f} B/s', 'green'))
                        time.sleep(3)
                        
                        with open(path+".out", 'wb') as fw:
                        	data = fw.write(data)
                        exit(0)

                        ltDecoder = decode.LtDecoder()
                        empty = True

                    else:
                        print(time.time())
            else:
                print(colored(str(time.time()), attrs=('dark',)))

            cv2.imshow('receiver', img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    finally:
        cap.release()
        cv2.destroyAllWindows()
