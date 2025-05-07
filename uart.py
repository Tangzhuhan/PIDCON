import time

class UART:
    def __init__(self, port, baudrate=9600, simulate=False):
        self.port = port
        self.baudrate = baudrate
        self.simulate = simulate
        if not self.simulate:
            import serial
            self.serial = serial.Serial(port, baudrate, timeout=1)
            time.sleep(2)  # 等待串口初始化

    def send_command(self, command):
        """发送命令"""
        try:
            self.serial.write(command)
            return True
        except Exception as e:
            print(f"发送命令失败: {e}")
            return False

    def read_data(self, size=10):
        """读取数据"""
        try:
            data = self.serial.read(size)
            return data
        except Exception as e:
            print(f"读取数据失败: {e}")
            return None

    def close(self):
        if not self.simulate:
            self.serial.close()