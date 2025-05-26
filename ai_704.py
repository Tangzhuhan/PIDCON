from uart import UART
import time

class AI704:
    def __init__(self, port, baudrate=9600, simulate=False):
        self.uart = UART(port, baudrate, simulate=simulate)

    def get_temp_channel_1(self):
        """读取通道1的温度"""
        return self._decode_temp(self._read_channel(1))

    def get_temp_channel_2(self):
        """读取通道2的温度"""
        return self._decode_temp(self._read_channel(2))

    def get_temp_channel_3(self):
        """读取通道3的温度"""
        return self._decode_temp(self._read_channel(3))

    def get_temp_channel_4(self):
        """读取通道4的温度"""
        return self._decode_temp(self._read_channel(4))

    def _decode_temp(self, data):
        """解码温度数据"""
        if not data:
            return None
        try:
            # 将字节数据转换为整数
            temp_int = int.from_bytes(data, byteorder='big', signed=True)
            # 转换为温度值
            return temp_int / 10.0
        except Exception as e:
            print(f"解码温度数据失败: {e}")
            return None

    def close(self):
        """关闭串口"""
        self.uart.close()