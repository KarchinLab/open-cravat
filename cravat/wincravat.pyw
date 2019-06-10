#!/usr/bin/env python

from infi.systray import SysTrayIcon
import threading
import subprocess
import time
import os
import queue
import tkinter
import tkinter.scrolledtext

# global variables
stop_event = None
log_window = None
log_window_close_signal = False
log_window_thread = None
wcravat_stdout_queue = None
wcravat_reader_thread = None
wcravat_log_writer_thread = None
stop_event = threading.Event()
wcravat_process = None

# log window functions

def launch_log_window ():
    global log_window
    log_window = tkinter.Tk(className='OpenCRAVAT')
    log_window.protocol('WM_DELETE_WINDOW', log_window.withdraw)
    scrt = tkinter.scrolledtext.ScrolledText(log_window, wrap='word')
    scrt.pack(side=tkinter.LEFT)
    log_window.after(1000, log_window_stop)
    log_window.withdraw()
    log_window.mainloop()

def log_window_stop ():
    global log_window
    global log_window_close_signal
    if log_window_close_signal == True:
        log_window.destroy()
    else:
        log_window.after(1000, log_window_stop)

# wcravat process

class LogReader (threading.Thread):
    def __init__ (self, event):
        threading.Thread.__init__(self)
        self.stopped = event

    def run (self):
        global wcravat_process
        for line in iter(wcravat_process.stdout.readline, b''):
            line = line.decode('utf-8').rstrip()
            wcravat_stdout_queue.put_nowait(line)

# log writer class

class LogWriter (threading.Thread):
    def __init__ (self, event):
        threading.Thread.__init__(self)
        self.stopped = event

    def run (self):
        while True:
            if self.stopped.is_set():
                break
            self.stopped.wait(0.5)
            global wcravat_stdout_queue
            global log_window
            while wcravat_stdout_queue.empty() == False:
                line = wcravat_stdout_queue.get()
                log_window.winfo_children()[0].winfo_children()[1].insert(tkinter.END, line + '\n')

# system tray functions
    
def show_log (arg):
    global log_window
    log_window.deiconify()

def hide_log (arg):
    global log_window
    log_window.withdraw()

def on_quit_callback (arg):
    global log_window_close_signal
    log_window_close_signal = True
    global stop_event
    stop_event.set()
    global wcravat_process
    subprocess.Popen("TASKKILL /F /PID {pid} /T".format(pid=wcravat_process.pid))

def main ():
    global stop_event
    global log_window
    global log_window_close_signal
    global log_window_thread
    global wcravat_stdout_queue
    global wcravat_reader_thread
    global wcravat_log_writer_thread
    global wcravat_process

    # log window
    log_window_thread = threading.Thread(target=launch_log_window)
    log_window_thread.start()

    # wcravat process
    # CREATE_NO_WINDOW is new in Python 3.7.
    wcravat_stdout_queue = queue.Queue()
    wcravat_process = subprocess.Popen(
        ['wcravat'],
        stdout=subprocess.PIPE, 
        stderr=subprocess.STDOUT, 
        creationflags=subprocess.CREATE_NO_WINDOW,
        shell=True
    )

    # wcravat reader
    wcravat_reader_thread = LogReader(stop_event)
    wcravat_reader_thread.start()

    # wcravat log writer
    wcravat_log_writer_thread = LogWriter(stop_event)
    wcravat_log_writer_thread.start()

    menu_options = (
        ('Show log', None, show_log),
        ('Hide log', None, hide_log),)
    systray = SysTrayIcon(
        "icon_256x256.ico", 
        "OpenCRAVAT", 
        menu_options, 
        on_quit=on_quit_callback,
        default_menu_index=0,
    )
    systray.start()

    log_window_thread.join()
    wcravat_reader_thread.join()
    wcravat_log_writer_thread.join()

if __name__ == '__main__':
    main()
