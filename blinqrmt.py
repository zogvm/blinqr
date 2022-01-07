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
import queue
import multiprocessing 
import math

#用RGB 3色 效果不好 太模糊了
useRGB=False 
#debug调试
isDebug=False
#3个二维码同时显示 效果不好 大部分只能识别到2张，还不如2个同屏
isThree=False
#用6KW像素的摄像头 可以10FPS
CAMERA6KW=True

def fix_scaling():
    import sys
    if sys.platform == 'win32':
        try:
            import ctypes
            PROCESS_SYSTEM_DPI_AWARE = 1
            ctypes.OleDLL('shcore').SetProcessDpiAwareness(PROCESS_SYSTEM_DPI_AWARE)
        except (ImportError, AttributeError, OSError):
            pass

#弹出选文件
def select_file():
    root = Tk()
    root.withdraw()
    path = askopenfilename()
    root.destroy()
    return path

#计算SHA
def calculate_sha1(data: bytes) -> str:
    m = sha1()
    m.update(data)
    return m.hexdigest()

#========================send==========start========================
#是否结束
isEnd=False
#将BYTE转块
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

#块转二维码 白底黑值
def block2img(block):
    block_encoded = b85encode(block)
    #b85encode       
    #2350 l  
    #1024 m
    #512  h
    #make_qr最耗 差不多0.2S
    qr = make_qr(block_encoded, error='l') #177*177
    img = ~np.array(qr.matrix, dtype=np.bool)
    img = np.uint8(img) * 0xFF
    img = np.pad(img, pad_width=9,mode='constant', constant_values=0xFF)
    return img

#块转二维码 不反色 黑底白值
def block2img_rgb(block):
    block_encoded = b85encode(block)
    #b85encode       
    #2350 l  
    #1024 m
    #512  h
    #make_qr最耗 差不多0.2S
    qr = make_qr(block_encoded, error='l') #177*177
    img = np.array(qr.matrix, dtype=np.bool)
    img = np.uint8(img) * 0xFF
    img = np.pad(img, pad_width=9,mode='constant', constant_values=0x00)
    return img
    
#块转二维码
def set_img(index,q_block,q_img):
    global isEnd   
    
    #用RGB分色
    if useRGB:
        i=0
        img_i = queue.Queue(30)
        while True:
            if q_block.qsize()>0:	
                if isDebug:	
                    start_time = time.time()
                block=q_block.get()
                img_i.put(block2img_rgb(block))
                i+=1
                #集齐3通道
                if i==3:
                    r=img_i.get()
                    g=img_i.get()
                    b=img_i.get()
                    # #如果 R G都有 则白
                    # #否则 就没有
                    # a = r.astype(np.float)
                    # c= g.astype(np.float)
                    # b=a+c
                    # b = b/400.0
                    # b = b.astype(np.int)
                    # b= b*254.0
                    # # ii=0
                    # # for item in b:
                    # #     ii+=1
                    # #     if ii==119:
                    # #         print(item)
                    # #         break
                    # b = b.astype(np.uint8)
                    #b=np.zeros(g.shape, np.uint8)
                    #https://blog.csdn.net/fripy/article/details/86658002
                    img = np.dstack((r,g,b))
                    q_img.put(img,True)
                    i=0
            
                if isDebug:
                    end_time = time.time()
                    print("index={:d},img time:{:.2f}".format(index,end_time-start_time))
            
            else:
                time.sleep(0.001)	
                if isEnd:
                    break
    else:
        #单色
        while True:
            if q_block.qsize()>0:	
                if isDebug:	
                    start_time = time.time()	
                block=q_block.get()
                img=block2img(block)
                q_img.put(img,True)
            
                if isDebug:
                    end_time = time.time()
                    print("index={:d},img time:{:.2f}".format(index,end_time-start_time))
            
            else:
                time.sleep(0.001)	
                if isEnd:
                    break
#发送端
def send(data: bytes, *, block_size: int = 2350):
    assert block_size <= 2350

    global isEnd  
    sha1 = calculate_sha1(data)
    stream = BytesIO(data)
    print(colored(f'多进程模式{len(data)} bytes, SHA-1: {sha1},useRGB:{useRGB}', 'blue'))
    
    root = Tk()
    screen_h= root.winfo_screenheight()
    screen_w= root.winfo_screenwidth()
    #计算是否显示2个二维码
    if screen_h> screen_w:
        if screen_h/screen_w >16.0/10.1: #16:9
            win_s=screen_w-80
            is_two=True
            if win_s>screen_h/2:
                win_s=screen_h/2
        else:
            win_s=screen_w-80
            is_two=False
        if isThree:
             win_s=screen_h/3
    else:
        if screen_w/screen_h >16.0/10.1:#16:9
            win_s=screen_h-80
            is_two=True
            if win_s>screen_w/2:
                win_s=screen_w/2
        else:
            win_s=screen_h-80
            is_two=False
        if isThree:
             win_s=screen_w/3

    win_s=win_s-10

    print("w:{:f},h:{:f},win:{:f},two:{:d}".format(screen_w,screen_h,win_s,is_two))

    cv2.namedWindow('sender1', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('sender1',int(win_s),int(win_s))
    cv2.moveWindow('sender1',0,0)

    if is_two:
        cv2.namedWindow('sender2', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('sender2',int(win_s),int(win_s)) 
        cv2.moveWindow('sender2',int(win_s)+10,0)
    if isThree:
        cv2.namedWindow('sender3', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('sender3',int(win_s),int(win_s)) 
        cv2.moveWindow('sender3',(int(win_s)+10)*2,0)

    start_time = time.time()
    i=0     
    q_block = multiprocessing.Queue(50)
    q_img = multiprocessing.Queue(50)
    t1 = multiprocessing.Process(target=set_block,args=[stream,block_size,q_block])
    t1.start()

    #设为5差不多为15FPS
    if useRGB or CAMERA6KW:
        ps=8
    else:
        ps=4
    for x in range(ps):
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
        if isThree:
            if q_img.qsize()>0:	
                i+=1
                print("time:{:.2f},{:d}".format(time.time()-start_time,i))
                img3=q_img.get()
                cv2.imshow('sender3', img3)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

                if useRGB and isDebug:
                    (b, g, r) = cv2.split(img2)
                    inv_b=cv2.bitwise_not(b)
                    inv_g=cv2.bitwise_not(g)
                    inv_r=cv2.bitwise_not(r)

                    cv2.imshow('sender1', inv_b)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                    time.sleep(0.3)
                    cv2.imshow('sender1', inv_g)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                    time.sleep(0.3)
                    cv2.imshow('sender1', inv_r)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                    time.sleep(0.3)

        #不要太快 会糊
        #可以双屏10FPS 受限CPU 帧率快不了
        if CAMERA6KW:
             time.sleep(0.1)
        #限成5FPS 	
        else:
            time.sleep(0.2)	
           
    cv2.destroyAllWindows()  
    isEnd=True

 #====================send=========end=================   

 #====================receive======start================    
 #视频流转图片
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
        #用RGB分通道 且反色
        if useRGB:
            (b, g, r) = cv2.split(img)
            inv_b=cv2.bitwise_not(b)
            q_img.put(inv_b,True)
            inv_g=cv2.bitwise_not(g)
            q_img.put(inv_g,True)
            inv_r=cv2.bitwise_not(r)
            q_img.put(inv_r,True)

            if isDebug:
                cv2.imshow('receive', img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                time.sleep(0.3)
                cv2.imshow('receive', inv_b)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                time.sleep(0.3)
                cv2.imshow('receive', inv_g)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                time.sleep(0.3)
                cv2.imshow('receive', inv_r)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                time.sleep(0.3)
        else:
            q_img.put(img,True)
        #time.sleep(0.03)  #33fps for realtime 
        time.sleep(0.001)

        if isEnd:
            break

        i+=1
        print("f time:{:.2f},{:d}".format(time.time()-start_time,i))
       

    cap.release()       
    isEnd=True

#识别图片是否为二维码
def decoded_img(lock,decode_i,index,q_img,q_decode):
    global isEnd 
    while True:
        if isEnd:
            break  
        time.sleep(0.001)	
        if q_img.qsize()>0:	

            #if isDebug:
            if True:
                start_time = time.time()

            img=q_img.get()
            decoded_qrs = pyzbar.decode(img, symbols=(pyzbar.ZBarSymbol.QRCODE,))

            #如果不是RGB分色
            if not useRGB:
                #转灰色    
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
                    
            #if isDebug:
            if True:
                with lock:
                    decode_i.value  +=1
                if decoded_qrs:
                    print("有识别到{:d}张 index={:d},decode time:{:.2f},i:{:d}".format(len(decoded_qrs),index,time.time()-start_time,decode_i.value))
                else:
                    print("未识别到 index={:d},decode time:{:.2f},i:{:d}".format(index,time.time()-start_time,decode_i.value))

            
#将识别后的二维码转换成BYTE
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

     
#接收视频
def receive(path):
    print(colored(f'多进程模式 useRGB:{useRGB}', 'blue'))
    global isEnd       
    ltDecoder = decode.LtDecoder()
    consume_num = 0

    lock=multiprocessing.Lock() #进程锁
    decode_i = multiprocessing.Value('i', 0)#进程共享变量
    #进程队列
    q_img = multiprocessing.Queue(50)
    q_decode = multiprocessing.Queue(50)
    q_block = multiprocessing.Queue(50)
   
    #多进程
    t1 = multiprocessing.Process(target=read_cap,args=[path,q_img])
    t1.start()
 
    for x in range(16):
        t2 = multiprocessing.Process(target=decoded_img,args=[lock,decode_i,x,q_img,q_decode])
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
                #加入LT解码块
                ltDecoder.consume_block(block)
                consume_num +=1
                #解码完成
                if ltDecoder.is_done():
                    #解析
                    data = ltDecoder.bytes_dump()
                    sha1 = calculate_sha1(data)
                    #打印
                    time_elapsed = time.time() - start_time
                    transfer_speed = len(data) / time_elapsed
                    print(colored(f'done:{len(data)} bytes, SHA-1: {sha1}', 'green'))
                    print(colored(f'done:{time_elapsed:.2f} seconds, {transfer_speed:.2f} B/s,consume_num:{consume_num:d}', 'green'))
                    #写文件
                    with open(path+".out", 'wb') as fw:
                        data = fw.write(data)
                    #仅支持单文件的在此结束和退出    
                    isEnd=True
                    break
                    #下一个    
                    ltDecoder = decode.LtDecoder()
                    consume_num = 0
            else:
                time.sleep(0.001)
    finally:
        cv2.destroyAllWindows()
    #更新结束标记
    isEnd=True

 #====================receive======end================    