#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-

############################################################
# Written by N.U @ Takada Laboratory on 2018.04.16
#
# Environment:  Python 3.4.2
#               OS: Raspbian 8.0 (jessie)
#               on Raspberry Pi 3
# Used sensor: MPU-9250(9軸センサ),BME-280(温度、湿度、気圧センサ)
#
#
# PythonからI2C をコントロールするためのライブラリ「wiringpi2」のインストール必要。
#    $ sudo pip install wiringpi2
# 起動方法
# pi@raspberrypi ~ $ sudo python cs17_wpi3_2sensors.py
#
# データ計測時間は　SAMPLING_TIME x TIMES
############################################################

import sys  # sysモジュールの呼び出し
import wiringpi as wi  # wiringPiモジュールの呼び出し
import time  # timeライブラリの呼び出し
import datetime  # datetimeモジュールの呼び出し
import os
import serial
import codecs
# データ計測時間は　SAMPLING_TIME x TIMES
SAMPLING_TIME = 0.1  # データ取得の時間間隔[sec]
TIMES = 100  # データの計測回数

wi.wiringPiSetup()  # wiringPiの初期化
i2c = wi.I2C()  # i2cの初期化

########################bme280 settings start#############################
i2c_address = 0x76  # #I2Cアドレス SDO=GND
# i2c_address = 0x77 # #I2Cアドレス SDO=VCC
bme280 = i2c.setup(i2c_address)  # i2cアドレス0x76番地をbme280として設定(アドレスは$sudo i2cdetect 1で見られる)

digT = []  # 配列を準備
digP = []  # 配列を準備
digH = []  # 配列を準備

temp = 0
humi = 0
press = 0
t_fine = 0.0


# レジスタへの書き込み
def writeReg(reg_address, data):
    i2c.writeReg8(bme280, reg_address, data)


# キャリブレーションデータの取得
def get_calib_param():
    calib = []

    for i in range(0x88, 0x88 + 24):
        calib.append(i2c.readReg8(bme280, i))
    calib.append(i2c.readReg8(bme280, 0xA1))
    for i in range(0xE1, 0xE1 + 7):
        calib.append(i2c.readReg8(bme280, i))

    digT.append((calib[1] << 8) | calib[0])
    digT.append((calib[3] << 8) | calib[2])
    digT.append((calib[5] << 8) | calib[4])
    digP.append((calib[7] << 8) | calib[6])
    digP.append((calib[9] << 8) | calib[8])
    digP.append((calib[11] << 8) | calib[10])
    digP.append((calib[13] << 8) | calib[12])
    digP.append((calib[15] << 8) | calib[14])
    digP.append((calib[17] << 8) | calib[16])
    digP.append((calib[19] << 8) | calib[18])
    digP.append((calib[21] << 8) | calib[20])
    digP.append((calib[23] << 8) | calib[22])
    digH.append(calib[24])
    digH.append((calib[26] << 8) | calib[25])
    digH.append(calib[27])
    digH.append((calib[28] << 4) | (0x0F & calib[29]))
    digH.append((calib[30] << 4) | ((calib[29] >> 4) & 0x0F))
    digH.append(calib[31])

    if digT[1] & 0x8000:
        digT[1] = (-digT[1] ^ 0xFFFF) + 1

    for i in range(1, 8):
        if digP[i] & 0x8000:
            digP[i] = (-digP[i] ^ 0xFFFF) + 1

    for i in range(6):
        if digH[i] & 0x8000:
            digH[i] = (-digH[i] ^ 0xFFFF) + 1
            #########################bme280 settings end####################


#########################GPS setting start######################
ser = serial.Serial(  # みちびき対応ＧＰＳ用の設定
    port="/dev/ttyAMA0",  # シリアル通信を用いる
    baudrate=9600,  # baudレート
    parity=serial.PARITY_NONE,  # パリティ
    bytesize=serial.EIGHTBITS,  # データのビット数
    stopbits=serial.STOPBITS_ONE,  # ストップビット数
    timeout=None,  # タイムアウト値
    xonxoff=0,  # ソフトウェアフロー制御
    rtscts=0,  # RTS/CTSフロー制御
)

# 後で使う変数をあらかじめ宣言
alt_lat_long = '0,0,0'  # GPSから得られる、高度、緯度、経度の情報
num_sat = '0'  # GPSから得られる、衛星の個数の情報


def sixty_to_ten(x):
    return x // 1 + x % 1 / 100 / 60


# GGA用のファイル初期化
with open('datagga.csv', 'w') as f:
    f.write('yyyy-mm-dd HH:MM:SS.ffffff ,a number of satellites ,high ,latitude ,longitude \n')  # 出力フォーマット

# GSV用のファイル初期化
with open('datagsv.csv', 'w') as f:
    f.write('No. ,Elevation in degrees ,degrees in true north \n')  # 仰角と方位角

now = datetime.datetime.now()
if os.path.exists("datagga.csv"):
    new_name = "datagga_{:%Y%m%d-%H%M%S}.csv".format(now)
    os.rename("datagga.csv", new_name)

# 出力フォーマット
print("yyyy-mm-dd HH:MM:SS.ffffff ,a number of satellites ,high ,latitude ,longitude")
print("No. ,Elevation in degrees ,degrees in true north \n")


#########################GPS setting end######################

#########################bme280 date get settings start####################
# データの取得
def readData():
    data = []
    global temp
    global humi
    global press
    for i in range(247, 255):
        data.append(i2c.readReg8(bme280, i))
    pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
    temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
    hum_raw = (data[6] << 8) | data[7]

    temp = compensate_T(temp_raw)
    press = compensate_P(pres_raw)
    humi = compensate_H(hum_raw)


# 気圧データを取得する
def compensate_P(adc_P):
    global t_fine
    pressure = 0.0

    v1 = (t_fine / 2.0) - 64000.0
    v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048) * digP[5]
    v2 = v2 + ((v1 * digP[4]) * 2.0)
    v2 = (v2 / 4.0) + (digP[3] * 65536.0)
    v1 = (((digP[2] * (((v1 / 4.0) * (v1 / 4.0)) / 8192)) / 8) + ((digP[1] * v1) / 2.0)) / 262144
    v1 = ((32768 + v1) * digP[0]) / 32768

    if v1 == 0:
        return 0
    pressure = ((1048576 - adc_P) - (v2 / 4096)) * 3125
    if pressure < 0x80000000:
        pressure = (pressure * 2.0) / v1
    else:
        pressure = (pressure / v1) * 2
    v1 = (digP[8] * (((pressure / 8.0) * (pressure / 8.0)) / 8192.0)) / 4096
    v2 = ((pressure / 4.0) * digP[7]) / 8192.0
    pressure = pressure + ((v1 + v2 + digP[6]) / 16.0)

    # print("pressure : %7.2f hPa" % (pressure/100))
    return pressure / 100


# 温度データを取得する
def compensate_T(adc_T):
    global t_fine
    v1 = (adc_T / 16384.0 - digT[0] / 1024.0) * digT[1]
    v2 = (adc_T / 131072.0 - digT[0] / 8192.0) * (adc_T / 131072.0 - digT[0] / 8192.0) * digT[2]
    t_fine = v1 + v2
    temperature = t_fine / 5120.0
    # print("temp : %-6.2f ℃" % (temperature))
    return temperature


# 湿度データを取得する
def compensate_H(adc_H):
    global t_fine
    var_h = t_fine - 76800.0
    if var_h != 0:
        var_h = (adc_H - (digH[3] * 64.0 + digH[4] / 16384.0 * var_h)) * (
            digH[1] / 65536.0 * (1.0 + digH[5] / 67108864.0 * var_h * (1.0 + digH[2] / 67108864.0 * var_h)))
    else:
        return 0
    var_h = var_h * (1.0 - digH[0] * var_h / 524288.0)
    if var_h > 100.0:
        var_h = 100.0
    elif var_h < 0.0:
        var_h = 0.0
    # print("hum : %6.2f ％" % (var_h))
    return var_h


# 設定
def setup():
    # osrs_t[2:0] 温度オーバーサンプリング設定
    # スキップ(output set to 0x80000)=0 オーバーサンプリング×1=1 オーバーサンプリング×2= 2 オーバーサンプリング×4= 3 オーバーサンプリング ×8=4 オーバーサンプリング ×16=5
    osrs_t = 1  # 温度オーバーサンプリング x 1
    # osrs_p[2:0] 気圧オーバーサンプリング 設定
    # スキップ(output set to 0x80000)=0 オーバーサンプリング ×1=1 オーバーサンプリング ×2=2    オーバーサンプリング ×4=3 オーバーサンプリング ×8=4 オーバーサンプリング ×16=5
    osrs_p = 3  # 気圧オーバーサンプリング x 4
    # osrs_h[2:0] 湿度オーバーサンプリング settings
    # スキップ(output set to 0x80000)=0 オーバーサンプリング ×1=1 オーバーサンプリング ×2=2    オーバーサンプリング ×4=3 オーバーサンプリング ×8=4 オーバーサンプリング ×16=5
    osrs_h = 0  # 湿度オーバーサンプリング Skipped
    mode = 3  # ノーマルモード (Sleep mode:0 Forced mode:1 Normal mode:3)
    # t_sb[2:0] tstandby [ms]
    # 0= 0.5[ms] 1= 62.5[ms] 2= 125[ms] 3= 250[ms] 4= 500[ms] 5= 1000[ms] 6= 10[ms] 7= 20[ms]
    t_sb = 0  # Tstandby 0.5ms
    # filter[2:0] Filter coefficient
    # 0= Filter off 1=coefficient2 2=coefficient4 3=coefficient8 4=coefficient 16
    filter = 4  # Filter coefficient 16
    spi3w_en = 0  # 3-wire SPI Disable

    ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
    config_reg = (t_sb << 5) | (filter << 2) | spi3w_en
    ctrl_hum_reg = osrs_h

    writeReg(0xF2, ctrl_hum_reg)
    writeReg(0xF4, ctrl_meas_reg)
    writeReg(0xF5, config_reg)


setup()
get_calib_param()
############################bme280 date get settings end#####################

############################mpu9250 settings start##########################
address = 0x68
addrAK8963 = 0x0C  # 磁気センサAK8963 アドレス
mpu9250 = i2c.setup(address)  # i2cアドレス0x68番地をmpu9250として設定(アドレスは$sudo i2cdetect 1で見られる)
AK8963 = i2c.setup(addrAK8963)
gyroRange = 1000  # 250, 500, 1000, 2000　'dps'から選択
accelRange = 8  # +-2, +-4, +-8, +-16 'g'から選択
magRange = 4912  # 'μT'

# センサ定数
REG_PWR_MGMT_1 = 0x6B
REG_INT_PIN_CFG = 0x37
REG_ACCEL_CONFIG1 = 0x1C
REG_ACCEL_CONFIG2 = 0x1D
REG_GYRO_CONFIG = 0x1B

MAG_MODE_POWERDOWN = 0  # 磁気センサpower down
MAG_MODE_SERIAL_1 = 1  # 磁気センサ8Hz連続測定モード
MAG_MODE_SERIAL_2 = 2  # 磁気センサ100Hz連続測定モード
MAG_MODE_SINGLE = 3  # 磁気センサ単発測定モード
MAG_MODE_EX_TRIGER = 4  # 磁気センサ外部トリガ測定モード
MAG_MODE_SELF_TEST = 5  # 磁気センサセルフテストモード
MAG_ACCESS = False  # 磁気センサへのアクセス可否
MAG_MODE = 0  # 磁気センサモード
MAG_BIT = 16  # 磁気センサが出力するbit数

# オフセット用変数
offsetAccelX = 0
offsetAccelY = 0
offsetAccelZ = 0
offsetGyroX = 0
offsetGyroY = 0
offsetGyroZ = 0


# レジスタを初期設定に戻す。
def resetRegister():
    global MAG_ACCESS
    if MAG_ACCESS == True:
        i2c.writeReg8(AK8963, 0x0B, 0x01)
    i2c.writeReg8(mpu9250, 0x6B, 0x80)
    MAG_ACCESS = False
    time.sleep(0.1)


# センシング可能な状態にする。
def powerWakeUp():
    # PWR_MGMT_1をクリア
    i2c.writeReg8(mpu9250, REG_PWR_MGMT_1, 0x00)
    time.sleep(0.1)
    # I2Cで磁気センサ機能(AK8963)へアクセスできるようにする(BYPASS_EN=1)
    i2c.writeReg8(mpu9250, REG_INT_PIN_CFG, 0x02)
    global MAG_ACCESS
    MAG_ACCESS = True
    time.sleep(0.1)


# 加速度の測定レンジを設定
# val = 16, 8, 4, 2(default)
val = 8


def setAccelRange(val, _calibration=False):
    # +-2g (00), +-4g (01), +-8g (10), +-16g (11)
    if val == 16:
        accelRange = 16
        _data = 0x18
    elif val == 8:
        accelRange = 8
        _data = 0x10
    elif val == 4:
        accelRange = 4
        _data = 0x08
    else:
        accelRange = 2
        _data = 0x00
    print("set accelRange=%d [g]" % accelRange)
    i2c.writeReg8(mpu9250, REG_ACCEL_CONFIG1, _data)
    accelCoefficient = accelRange / float(0x8000)
    time.sleep(0.1)

    # オフセット値をリセット
    # offsetAccelX       = 0
    # offsetAccelY       = 0
    # offsetAccelZ       = 0

    # Calibration
    if _calibration == True:
        calibAccel(1000)
    return

    # ジャイロの測定レンジを設定します。
    # val= 2000, 1000, 500, 250(default)


def setGyroRange(val, _calibration=False):
    if val == 2000:
        gyroRange = 2000
        _data = 0x18
    elif val == 1000:
        gyroRange = 1000
        _data = 0x10
    elif val == 500:
        gyroRange = 500
        _data = 0x08
    else:
        gyroRange = 250
        _data = 0x00
    print("set gyroRange=%d [dps]" % gyroRange)
    i2c.writeReg8(mpu9250, REG_GYRO_CONFIG, _data)
    gyroCoefficient = gyroRange / float(0x8000)
    time.sleep(0.1)

    # Reset offset value (so that the past offset value is not inherited)
    # offsetGyroX        = 0
    # offsetGyroY        = 0
    # offsetGyroZ        = 0

    # Calibration
    if _calibration == True:
        calibGyro(1000)
    return


# 磁気センサのレジスタを設定する
def setMagRegister(_mode, _bit):
    global MAG_ACCESS
    global MAG_MODE
    if MAG_ACCESS == False:
        # 磁気センサへのアクセスが有効になっていない場合は例外
        raise Exception('001 Access to a sensor is invalid.')

    _writeData = 0x00
    # 測定モードの設定
    if _mode == '8Hz':  # Continuous measurement mode 1
        _writeData = 0x02
        MAG_MODE = MAG_MODE_SERIAL_1
    elif _mode == '100Hz':  # Continuous measurement mode 2
        _writeData = 0x06
        MAG_MODE = MAG_MODE_SERIAL_2
    elif _mode == 'POWER_DOWN':  # Power down mode
        _writeData = 0x00
        MAG_MODE = MAG_MODE_POWERDOWN
    elif _mode == 'EX_TRIGER':  # Trigger measuremen...
        _writeData = 0x04
        MAG_MODE = MAG_MODE_EX_TRIGER
    elif _mode == 'SELF_TEST':  # self test mode
        _writeData = 0x08
        MAG_MODE = MAG_MODE_SELF_TEST
    else:  # _mode='SINGLE'    # single measurment mode
        _writeData = 0x01
        MAG_MODE = MAG_MODE_SINGLE

        # 出力するbit数
    if _bit == '14bit':  # output 14bit
        _writeData = _writeData | 0x00
        MAG_BIT = 14
    else:  # _bit='16bit'      # output 16bit
        _writeData = _writeData | 0x10
        MAG_BIT = 16
    print("set MAG_MODE=%s, %d bit" % (_mode, MAG_BIT))
    i2c.writeReg8(AK8963, 0x0A, _writeData)  # センサからのデータはそのまま使おうとするとunsignedとして扱われるため、signedに変換(16ビット限定）


def u2s(unsigneddata):
    if unsigneddata & (0x01 << 15):
        return -((unsigneddata ^ 0xffff) + 1)
    return unsigneddata


#################################mpu9250 settings end###################

#################################mpu9250 date get settings start#########################
# 加速度値を取得
def getAccel():
    ACCEL_XOUT_H = i2c.readReg8(mpu9250, 0x3B)
    ACCEL_XOUT_L = i2c.readReg8(mpu9250, 0x3C)
    ACCEL_YOUT_H = i2c.readReg8(mpu9250, 0x3D)
    ACCEL_YOUT_L = i2c.readReg8(mpu9250, 0x3E)
    ACCEL_ZOUT_H = i2c.readReg8(mpu9250, 0x3F)
    ACCEL_ZOUT_L = i2c.readReg8(mpu9250, 0x40)
    rawX = accelCoefficient * u2s(ACCEL_XOUT_H << 8 | ACCEL_XOUT_L) + offsetAccelX
    rawY = accelCoefficient * u2s(ACCEL_YOUT_H << 8 | ACCEL_YOUT_L) + offsetAccelY
    rawZ = accelCoefficient * u2s(ACCEL_ZOUT_H << 8 | ACCEL_ZOUT_L) + offsetAccelZ
    # data    = i2c.readReg8(address, 0x3B )
    # print "getaccell data=%d"%data
    # rawX    = accelCoefficient * u2s(data[0] << 8 | data[1]) + offsetAccelX
    # rawY    = accelCoefficient * u2s(data[2] << 8 | data[3]) + offsetAccelY
    # rawZ    = accelCoefficient * u2s(data[4] << 8 | data[5]) + offsetAccelZ
    return rawX, rawY, rawZ


# ジャイロ値を取得
def getGyro():
    GYRO_XOUT_H = i2c.readReg8(mpu9250, 0x43)
    GYRO_XOUT_L = i2c.readReg8(mpu9250, 0x44)
    GYRO_YOUT_H = i2c.readReg8(mpu9250, 0x45)
    GYRO_YOUT_L = i2c.readReg8(mpu9250, 0x46)
    GYRO_ZOUT_H = i2c.readReg8(mpu9250, 0x47)
    GYRO_ZOUT_L = i2c.readReg8(mpu9250, 0x48)
    rawX = gyroCoefficient * u2s(GYRO_XOUT_H << 8 | GYRO_XOUT_L) + offsetGyroX
    rawY = gyroCoefficient * u2s(GYRO_YOUT_H << 8 | GYRO_YOUT_L) + offsetGyroY
    rawZ = gyroCoefficient * u2s(GYRO_ZOUT_H << 8 | GYRO_ZOUT_L) + offsetGyroZ
    # data    =  i2c.readReg8(address, 0x43 )
    # rawX    = gyroCoefficient * u2s(data[0] << 8 | data[1]) + offsetGyroX
    # rawY    = gyroCoefficient * u2s(data[2] << 8 | data[3]) + offsetGyroY
    # rawZ    = gyroCoefficient * u2s(data[4] << 8 | data[5]) + offsetGyroZ
    return rawX, rawY, rawZ


# 磁気値を取得
def getMag():
    global MAG_ACCESS
    if not MAG_ACCESS:
        # 磁気センサへのアクセスが有効になっていない場合は例外
        raise Exception('002 Access to a sensor is invalid.')

    # 事前処理
    global MAG_MODE
    if MAG_MODE == MAG_MODE_SINGLE:
        # 単発測定モードは測定終了と同時にPower Downになるので、もう一度モードを変更する
        if MAG_BIT == 14:  # output 14bit
            _writeData = 0x01
        else:  # output 16bit
            _writeData = 0x11
        i2c.writeReg8(AK8963, 0x0A, _writeData)
        time.sleep(0.01)

    elif MAG_MODE == MAG_MODE_SERIAL_1 or MAG_MODE == MAG_MODE_SERIAL_2:
        status = i2c.readReg8(AK8963, 0x02)
        if (status & 0x02) == 0x02:
            # if (status[0] & 0x02) == 0x02:
            # データオーバーランがあるので再度センシング
            i2c.readReg8(AK8963, 0x09)

    elif MAG_MODE == MAG_MODE_EX_TRIGER:
        # 未実装
        return

    elif MAG_MODE == MAG_MODE_POWERDOWN:
        raise Exception('003 Mag sensor power down')

    # ST1レジスタを確認してデータ読み出しが可能か確認する
    status = i2c.readReg8(AK8963, 0x02)
    while (status & 0x01) != 0x01:
        # while (status[0] & 0x01) != 0x01:
        # Wait until data ready state.
        time.sleep(0.01)
        status = i2c.readReg8(AK8963, 0x02)

    # データ読み出し
    MAG_XOUT_L = i2c.readReg8(AK8963, 0x03)
    MAG_XOUT_H = i2c.readReg8(AK8963, 0x04)
    MAG_YOUT_L = i2c.readReg8(AK8963, 0x05)
    MAG_YOUT_H = i2c.readReg8(AK8963, 0x06)
    MAG_ZOUT_L = i2c.readReg8(AK8963, 0x07)
    MAG_ZOUT_H = i2c.readReg8(AK8963, 0x08)
    MAG_OF = i2c.readReg8(AK8963, 0x09)
    rawX = u2s(MAG_XOUT_H << 8 | MAG_XOUT_L)
    rawY = u2s(MAG_YOUT_H << 8 | MAG_YOUT_L)
    rawZ = u2s(MAG_ZOUT_H << 8 | MAG_ZOUT_L)
    st2 = MAG_OF
    # data    = i2c.readReg8(addrAK8963, 0x03 ,7)
    # rawX    = u2s(data[1] << 8 | data[0])  # Lower bit is ahead.
    # rawY    = u2s(data[3] << 8 | data[2])  # Lower bit is ahead.
    # rawZ    = u2s(data[5] << 8 | data[4])  # Lower bit is ahead.
    # st2     = data[6]

    # オーバーフローチェック
    if (st2 & 0x08) == 0x08:
        # オーバーフローのため正しい値が得られていない
        raise Exception('004 Mag sensor over flow')

    # μTへの変換
    if MAG_BIT == 16:  # output 16bit
        rawX = rawX * magCoefficient16
        rawY = rawY * magCoefficient16
        rawZ = rawZ * magCoefficient16
    else:  # output 14bit
        rawX = rawX * magCoefficient14
        rawY = rawY * magCoefficient14
        rawZ = rawZ * magCoefficient14

    return rawX, rawY, rawZ


# 加速度センサを較正する
# 本当は緯度、高度、地形なども考慮する必要があるとは思うが、簡略で。
# z軸方向に正しく重力がかかっており、重力以外の加速度が発生していない前提
def calibAccel(_count=1000):
    print("Accel calibration start")
    _sum = [0, 0, 0]

    # データのサンプルを取る
    for _i in range(_count):
        _data = getAccel()
        _sum[0] += _data[0]
        _sum[1] += _data[1]
        _sum[2] += _data[2]

        # 平均値をオフセットにする
    global offsetAccelX, offsetAccelY, offsetAccelZ
    offsetAccelX = -1.0 * _sum[0] / _count
    offsetAccelY = -1.0 * _sum[1] / _count
    offsetAccelZ = -1.0 * ((_sum[2] / _count) - 1.0)  # 重力分を差し引く

    # I want to register an offset value in a register. But I do not know the behavior, so I will put it on hold.
    print("Accel calibration complete")
    return offsetAccelX, offsetAccelY, offsetAccelZ


# ジャイロセンサを較正する
# 各軸に回転が発生していない前提
def calibGyro(_count=1000):
    print("Gyro calibration start")
    _sum = [0, 0, 0]

    # データのサンプルを取る
    for _i in range(_count):
        _data = getGyro()
        _sum[0] += _data[0]
        _sum[1] += _data[1]
        _sum[2] += _data[2]

    # 平均値をオフセットにする
    global offsetGyroX, offsetGyroY, offsetGyroZ
    offsetGyroX = -1.0 * _sum[0] / _count
    offsetGyroY = -1.0 * _sum[1] / _count
    offsetGyroZ = -1.0 * _sum[2] / _count

    # I want to register an offset value in a register. But I do not know the behavior, so I will put it on hold.
    print("Gyro calibration complete")
    return offsetGyroX, offsetGyroY, offsetGyroZ


####################mpu9250 date get settings end##################
if __name__ == '__main__':

    # bus     = smbus.SMBus(1)
    resetRegister()
    powerWakeUp()
    gyroCoefficient = gyroRange / float(0x8000)  # coefficient : sensed decimal val to dps val.
    accelCoefficient = accelRange / float(0x8000)  # coefficient : sensed decimal val to g val
    magCoefficient16 = magRange / 32760.0  # confficient : sensed decimal val to μT val (16bit)
    magCoefficient14 = magRange / 8190.0  # confficient : sensed decimal val to μT val (14bit)
    setAccelRange(accelRange, False)
    setGyroRange(gyroRange, False)
    setMagRegister('100Hz', '16bit')
    # ファイルへ書出し準備
    now = datetime.datetime.now()
    # 現在時刻を織り込んだファイル名を生成
    fmt_name = "/home/pi/data/cs17_wpi3_2sensors_logs_{0:%Y%m%d-%H%M%S}.csv".format(now)
    f_cs17_wpi3_2sensors = codecs.open(fmt_name, mode='w', encoding="utf-8")  # 書き込みファイル
    # f_cs17_wpi3_2sensors= open('home/pi/data/cs17_wpi3_2sensors_logs.csv', 'w')    #書き込みファイル
    value = u"yyyy-mm-dd hh:mm:ss.mmmmmm,T[℃],H[%],P[hPa],x[g],y[g],z[g],x[dps],y[dps],z[dps],x[uT],y[uT],z[uT],h[m]"  # header行への書き込み内容
    f_cs17_wpi3_2sensors.write(value + "\n")  # header行をファイル出力
    while True:  # データ取得時間制限あり
        try:
            # for _i in range(TIMES):		#データ取得時間制限なし
            date = datetime.datetime.now()  # now()メソッドで現在日付・時刻のdatetime型データの変数を取得 世界時：UTCnow
            now = time.time()  # 現在時刻の取得
            readData()
            acc = getAccel()  # 加速度値の取得
            gyr = getGyro()  # ジャイロ値の取得
            mag = getMag()  # 磁気値の取得
            h = (((1013.25 / press) ** (1 / 5.257) - 1) * (temp + 273.15)) / 0.0065

            # ファイルへ書出し
            value = "%s,%6.2f,%6.2f,%7.2f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%4.4f" % (
            date, temp, humi, press, acc[0], acc[1], acc[2], gyr[0], gyr[1], gyr[2], mag[0], mag[1], mag[2],
            h)  # 時間、xyz軸回りの加速度
            f_cs17_wpi3_2sensors.write(value + "\n")  # ファイルを出力
            print(value)  # 標準出力
            # 指定秒数の一時停止
            sleepTime = SAMPLING_TIME - (time.time() - now)
            if sleepTime < 0.0:
                continue
            time.sleep(sleepTime)
        except KeyboardInterrupt:
            break
    f_cs17_wpi3_2sensors.close()  # 書き込みファイルを閉じる
