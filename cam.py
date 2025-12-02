from pioneer_sdk import Camera
import cv2
import numpy as np
import time
from multiprocessing import shared_memory
import struct
import signal
import sys

def signal_handler(sig, frame):
    """Обработчик сигнала для корректного завершения"""
    print("\nЗавершение работы камеры...")
    if 'shm' in globals():
        shm.close()
        shm.unlink()
    sys.exit(0)

if __name__ == "__main__":
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    
    camera = Camera()
    shm_name = "pioneer_frame"
    
    # Создаем shared memory в файле с камерой
    try:
        shm = shared_memory.SharedMemory(name=shm_name, create=True, size=1920*1080*3 + 12)
        print("Shared memory created for camera")
    except FileExistsError:
        shm = shared_memory.SharedMemory(name=shm_name)
        print("Shared memory connected for camera")
    
    # Счетчик кадров для сохранения
    frame_counter = 0
    save_interval = 50  # Сохранять каждый 100-й кадр
    
    try:
        while True:
            frame = camera.get_frame()
            
            if frame is not None:
                camera_frame = cv2.imdecode(
                    np.frombuffer(frame, dtype=np.uint8), cv2.IMREAD_COLOR
                )
                
                if camera_frame is not None:
                    height, width = camera_frame.shape[:2]
                    
                    # Упаковываем размеры кадра в заголовок (3 int по 4 байта = 12 байт)
                    header = struct.pack('iii', width, height, len(camera_frame.tobytes()))
                    frame_data = camera_frame.tobytes()
                    
                    # Записываем заголовок и данные кадра в shared memory (каждый кадр)
                    shm.buf[:12] = header  # первые 12 байт - заголовок
                    shm.buf[12:12+len(frame_data)] = frame_data
                    
                    # Сохраняем кадр только каждый 100-й кадр
                    frame_counter += 1
                    if frame_counter >= save_interval:
                        cv2.imwrite('frame.jpg', camera_frame)
                        print(f"Кадр {frame_counter} сохранен как frame.jpg в {time.strftime('%H:%M:%S')}")
                        frame_counter = 0  # Сбрасываем счетчик
            
            time.sleep(0.033)  # ~30 FPS - отправляем каждый кадр в shared memory
                
    except Exception as e:
        print(f"Error in camera stream: {e}")
    finally:
        # Корректно закрываем ресурсы
        shm.close()
        shm.unlink()
        print("Camera stream stopped")