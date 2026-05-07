import time
import functools
import logging
import psutil
import os



logging.basicConfig(
    filename='system_performance.log', #pou tha grfaontai ta logs
    level=logging.INFO, #info kai panw
    format='%(asctime)s - %(message)s'
)

def measure_performance(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):#vazei ola ta args se ena tuple, ta 2 kanoun ena dictionary, epeidh exw ram,cpu,xrono
     
        process = psutil.Process(os.getpid())#pairneis to procces, to python script kai me afto metras RAM,CPU
        

        mem_before = process.memory_info().rss / 1024 / 1024  #MB prin treksei h synarthsh
        process.cpu_percent(interval=None) #Καθαρισμός του counter
        start_time = time.time()
        
       
        result = func(*args, **kwargs)#trexei h pragmatikh synarthsh pou metraw
       
        

        end_time = time.time()#pote teleiwse
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        cpu_usage = process.cpu_percent(interval=None)
        

        execution_time = (end_time - start_time) * 1000 # ms
        mem_diff = mem_after - mem_before
        
        
        print(f"STATS for '{func.__name__}':")
        print(f"Time: {execution_time:.2f} ms")
        print(f"RAM:  {mem_after:.2f} MB ({mem_diff:+.2f} MB)")
        print(f"CPU:  {cpu_usage:.1f}%") 
        

        logging.info(f"METRICS,{func.__name__},Time={execution_time:.2f}ms,RAM={mem_after:.2f}MB,CPU={cpu_usage:.1f}%")
        
        return result
    return wrapper