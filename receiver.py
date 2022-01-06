from blinqrmt import fix_scaling,select_file, receive
#from blinqr import fix_scaling,select_file, receive

if __name__ == '__main__':
    fix_scaling()
    
    path = select_file()
    if not path:
        raise SystemExit
        
    receive(path)
