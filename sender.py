from blinqrmt import fix_scaling, select_file, send
#from blinqr import fix_scaling, select_file, send
import multiprocessing 

if __name__ == '__main__':
    multiprocessing.freeze_support()  #解决多进程打包pyinstall问题
    fix_scaling()

    path = select_file()
    if not path:
        raise SystemExit

    with open(path, 'rb') as f:
        data = f.read()

    send(data)
