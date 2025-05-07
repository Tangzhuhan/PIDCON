from uart import UART
import time
import serial

class PowerSupply:
    def __init__(self, port):
        """初始化电源发生器
        Args:
            port: 串口名称，如 'COM3' 或 '/dev/ttyUSB0'
        """
        self.port = port
        self.serial = None
        self.is_output_on = False  # 记录输出状态
        self.connect()

    def connect(self):
        """连接串口"""
        try:
            if self.serial and self.serial.is_open:
                self.serial.close()
            
            self.serial = serial.Serial(
                port=self.port,
                baudrate=9600,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=1
            )
            return True
        except Exception as e:
            print(f"连接电源发生器失败: {e}")
            return False

    def is_open(self):
        """检查串口是否打开"""
        return self.serial is not None and self.serial.is_open

    def set_voltage(self, voltage):
        """设置电压
        Args:
            voltage: 要设置的电压值，如 3.00
        Returns:
            bool: 设置是否成功
        """
        if not self.is_open():
            print("串口未打开")
            return False

        try:
            # 发送设置电压指令
            command = f"VOLT {voltage:.2f}\r\n"
            self.serial.write(command.encode())
            time.sleep(0.1)  # 等待设置完成

            # 验证设置是否成功
            self.serial.write(b"VOLT?\r\n")
            response = self.serial.readline().decode().strip()
            # 移除单位并转换为浮点数
            set_voltage = float(response.replace('V', '').strip())
            
            # 检查设置值是否在允许的误差范围内
            if abs(set_voltage - voltage) > 0.1:
                print(f"Warning: Set voltage {set_voltage} differs from target {voltage}")
                return False
                
            return True
        except Exception as e:
            print(f"Error setting voltage: {e}")
            return False

    def read_voltage(self):
        """读取实际电压值
        Returns:
            float: 电压值，读取失败返回None
        """
        if not self.is_open():
            print("串口未打开")
            return None

        try:
            self.serial.write(b"MEAS:VOLT?\r\n")
            response = self.serial.readline().decode().strip()
            # 移除单位并转换为浮点数
            voltage = float(response.replace('V', ''))
            return voltage
        except Exception as e:
            print(f"Error reading voltage: {e}")
            return None

    def read_current(self):
        """读取电流值"""
        try:
            response = self.serial.write(b'MEAS:CURR?\r\n')
            time.sleep(0.1)  # 等待响应
            current_str = self.serial.readline().decode('utf-8').strip()
            if current_str:
                # 移除单位并转换为浮点数
                current = float(current_str.replace('A', '').strip())
                return current
            return None
        except Exception as e:
            print(f"读取电流失败: {e}")
            return None

    def on_output(self):
        """开启输出"""
        if not self.is_open():
            print("串口未打开")
            return False

        try:
            # 发送开启输出命令
            command = b'OUTP ON\r\n'
            self.serial.write(command)
            time.sleep(0.1)  # 等待命令执行完成
            
            # 验证输出状态
            self.serial.write(b'OUTP?\r\n')
            response = self.serial.readline().decode().strip()
            if response == '1':
                self.is_output_on = True
                return True
            return False
        except Exception as e:
            print(f"开启输出失败: {e}")
            return False

    def off_output(self):
        """关闭输出"""
        if not self.is_open():
            print("串口未打开")
            return False

        try:
            # 发送关闭输出命令
            command = b'OUTP OFF\r\n'
            self.serial.write(command)
            time.sleep(0.1)  # 等待命令执行完成
            
            # 验证输出状态
            self.serial.write(b'OUTP?\r\n')
            response = self.serial.readline().decode().strip()
            if response == '0':
                self.is_output_on = False
                return True
            return False
        except Exception as e:
            print(f"关闭输出失败: {e}")
            return False

    def close(self):
        """关闭串口连接"""
        try:
            if self.is_output_on:
                self.off_output()
            if self.serial and self.serial.is_open:
                self.serial.close()
        except Exception as e:
            print(f"Error closing connection: {e}")