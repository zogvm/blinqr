from blinqrmt import fix_scaling,select_file, receive
#from blinqr import fix_scaling,select_file, receive
import multiprocessing 

if __name__ == '__main__':
    multiprocessing.freeze_support()  #解决多进程打包pyinstall问题
    fix_scaling()
    
    path = select_file()
    if not path:
        raise SystemExit
        
    receive(path)
