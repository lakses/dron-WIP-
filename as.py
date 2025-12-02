from pioneer_sdk import Pioneer
import cv2
import numpy as np
import time
import subprocess
import signal
import sys
from multiprocessing import shared_memory
import struct

def signal_handler(sig, frame):
    """Обработчик сигнала для корректного завершения"""
    print("\nЗавершение работы...")
    if 'camera_process' in globals():
        camera_process.terminate()
        camera_process.wait()
    if 'shm' in globals():
        shm.close()
    cv2.destroyAllWindows()
    sys.exit(0)

def draw_battery_info(frame, battery_level):
    """Отрисовка информации о батарее на кадре"""
    if battery_level is not None:
        text = f"Battery: {battery_level}%"
        cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, (0, 255, 0), 2)
    else:
        cv2.putText(frame, "Battery: N/A", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 
                   0.7, (0, 0, 255), 2)
    return frame

if __name__ == "__main__":
    # Регистрируем обработчик сигналов
    signal.signal(signal.SIGINT, signal_handler)
    
    print(
        """
    1 -- arm
    2 -- disarm
    3 -- takeoff
    4 -- land
    5 -- hover (зависнуть)
    ↶q  w↑  e↷    i-↑
    ←a      d→     k-↓
        s↓"""
    )
    
    # Запускаем файл с камерой
    try:
        camera_process = subprocess.Popen([sys.executable, "cam.py"])
        print("Камера запущена...")
        time.sleep(2)
    except Exception as e:
        print(f"Ошибка запуска камеры: {e}")
        sys.exit(1)
    
    # Подключаемся к shared memory
    shm_name = "pioneer_frame"
    try:
        shm = shared_memory.SharedMemory(name=shm_name)
        print("Connected to shared memory")
    except Exception as e:
        print(f"Ошибка подключения к shared memory: {e}")
        camera_process.terminate()
        sys.exit(1)
    
    pioneer_mini = Pioneer()
    min_v = 1300
    max_v = 1700
    
    # Переменная для режима зависания
    hover_mode = False
    
    # Создаем окно для камеры
    cv2.namedWindow("Camera Stream", cv2.WINDOW_NORMAL)
    
    # Переменные для управления
    last_battery_check = time.time()
    battery_level = None
    
    try:
        while True:
            ch_1 = 1500
            ch_2 = 1500
            ch_3 = 1500
            ch_4 = 1500
            ch_5 = 2000

            
            # Читаем кадр из shared memory
            try:
                header = shm.buf[:12]
                width, height, frame_size = struct.unpack('iii', header)
                
                if frame_size > 0:
                    frame_data = bytes(shm.buf[12:12+frame_size])
                    frame_array = np.frombuffer(frame_data, dtype=np.uint8)
                    camera_frame = frame_array.reshape((height, width, 3))
                    
                    # Получаем уровень батареи каждые 10 секунд
                    if time.time() - last_battery_check > 10:
                        battery_level = pioneer_mini.get_battery_status(get_last_received=True)
                        last_battery_check = time.time()
                    
                    # Добавляем информацию о батарее на кадр
                    camera_frame_with_battery = draw_battery_info(camera_frame.copy(), battery_level)
                    
                    # Отображаем кадр
                    cv2.imshow("Camera Stream", camera_frame_with_battery)
                    
            except Exception as e:
                pass
            
            # Управление дроном
            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                print("esc pressed")
                break
            elif key == ord("1"):
                print("Arming...")
                pioneer_mini.arm()
            elif key == ord("2"):
                print("Disarming...")
                pioneer_mini.disarm()
            elif key == ord("3"):
                print("Takeoff...")
                time.sleep(2)
                pioneer_mini.arm()
                time.sleep(1)
                pioneer_mini.takeoff()
                time.sleep(2)
            elif key == ord("4"):
                print("Landing...")
                time.sleep(2)
                pioneer_mini.land()
                time.sleep(2)
            elif key == ord("5"):
                hover_mode = not hover_mode
                if hover_mode:
                    print("HOVER MODE: ON")
                else:
                    print("HOVER MODE: OFF")
            elif key == ord("w"):
                print("Forward")
                ch_3 = min_v
            elif key == ord("s"):
                print("Backward")
                ch_3 = max_v
            elif key == ord("a"):
                print("Left")
                ch_4 = min_v
            elif key == ord("d"):
                print("Right")
                ch_4 = max_v
            elif key == ord("q"):
                print("Yaw left")
                ch_2 = 2000
            elif key == ord("e"):
                print("Yaw right")
                ch_2 = 1000
            elif key == ord("i"):
                print("Up")
                ch_1 = 2000
            elif key == ord("k"):
                print("Down")
                ch_1 = 1000
            
            # Если включен режим зависания - обнуляем управление
            if hover_mode:
                ch_1 = 1500
                ch_2 = 1500
                ch_3 = 1500
                ch_4 = 1500
            
            pioneer_mini.send_rc_channels(
                channel_1=ch_1,
                channel_2=ch_2,
                channel_3=ch_3,
                channel_4=ch_4,
                channel_5=ch_5,
            )
            time.sleep(0.02)
            
    except KeyboardInterrupt:
        print("Interrupted by user")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        # Останавливаем дрон
        print("Остановка дрона...")
        pioneer_mini.land()
        time.sleep(1)
        pioneer_mini.close_connection()
        
        # Закрываем процессы
        print("Остановка процессов...")
        camera_process.terminate()
        camera_process.wait()
        
        # Закрываем shared memory
        shm.close()
        
        cv2.destroyAllWindows()
        print("Все процессы остановлены")