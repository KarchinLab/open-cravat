import subprocess
import multiprocessing as mp
import sys
import datetime
import time

def run1(path):
    print('run1')
    p = mp.Process(target=run2,args=(path,))
    p.start()

def run2(path):
    print('run2')
    write_dt(path, 10)

def write_dt(path, n):
    print('write time to {} {} times'.format(path, n))
    with open(path,'w') as wf:
        for _ in range(n):
            time.sleep(1)
            wf.write(datetime.datetime.now().isoformat()+'\n')
            wf.flush()

if __name__ == '__main__':
    fname = sys.argv[1]
    # subprocess.call(['python','orphan.py',fname])
    p1 = mp.Process(target=run1,args=(fname,))
    p1.start()
    time.sleep(3)
    p1.terminate()