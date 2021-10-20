#!/usr/local/bin/python
# -*- coding: utf-8 -*-

import serial
import datetime
import time  # timeライブラリの呼び出し
import wiringpi as wi  # wiringPiモジュールの呼び出し
import os


# データ計測時間は　SAMPLING_TIME x TIMES
SAMPLING_TIME = 0.1  # データ取得の時間間隔[sec]
TIMES = 100  # データの計測回数

wi.wiringPiSetup()  # wiringPiの初期化
i2c = wi.I2C()  # i2cの初期化

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
    elif _mode == 'EX_TRIGER':  # Trigger measurement mode
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
    i2c.writeReg8(AK8963, 0x0A, _writeData)


# センサからのデータはそのまま使おうとするとunsignedとして扱われるため、signedに変換(16ビット限定）
def u2s(unsigneddata):
    if unsigneddata & (0x01 << 15):
        return -1 * ((unsigneddata ^ 0xffff) + 1)
    return unsigneddata


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
    if MAG_ACCESS == False:
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



ser = serial.Serial(               #みちびき対応ＧＰＳ用の設定
  port = "/dev/ttyS0",           #シリアル通信を用いる
  baudrate = 9600,                 #baudレート
  parity = serial.PARITY_NONE,     #パリティ
  bytesize = serial.EIGHTBITS,     #データのビット数
  stopbits = serial.STOPBITS_ONE,  #ストップビット数
  timeout = None,                  #タイムアウト値
  xonxoff = 0,                     #ソフトウェアフロー制御
  rtscts = 0,                      #RTS/CTSフロー制御
  )

#後で使う変数をあらかじめ宣言
alt_lat_long = '0,0,0'     #GPSから得られる、高度、緯度、経度の情報
num_sat = '0'   #GPSから得られる、衛星の個数の情報

def sixty_to_ten(x):
  ans = float(int(x) + ((x - int(x)))*100/60)
  return ans

#GGA用のファイル初期化
f = open('datagga.csv','w')
f.write('yyyy-mm-dd HH:MM:SS.ffffff ,a number of satellites ,high ,latitude ,longitude \n')  #出力フォーマット
f.close()

#GSV用のファイル初期化
f = open('datagsv.csv','w')
f.write('No. ,Elevation in degrees ,degrees in true north \n') #仰角と方位角
f.close()

now = datetime.datetime.now()
if os.path.exists("datagga.csv"):
  new_name = "{0}_{1:%Y%m%d-%H%M%S}.{2}".format("datagga",now,"csv")
  os.rename("datagga.csv",new_name)

#出力フォーマット
print ("yyyy-mm-dd HH:MM:SS.ffffff ,a number of satellites ,high ,latitude ,longitude")
print ("No. ,Elevation in degrees ,degrees in true north \n")

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
fmt_name = "/home/pi/data/mpu9250wpi_logs_{0:%Y%m%d-%H%M%S}.csv".format(now)
f_mpu9250 = open(fmt_name, 'w')  # 書き込みファイル
# f_mpu9250= open('home/pi/data/mpu9250wpi_logs.csv', 'w')    #書き込みファイル
value = "yyyy-mm-dd hh:mm:ss.mmmmmm, x[g],y[g],z[g],x[dps],y[dps],z[dps],x[uT],y[uT],z[uT]"  # header行への書き込み内容
f_mpu9250.write(value + "\n")  # header行をファイル出力

##############################################################################
while True:
    date = datetime.datetime.now()  # now()メソッドで現在日付・時刻のdatetime型データの変数を取得 世界時：UTCnow
    now = time.time()  # 現在時刻の取得
    acc = getAccel()  # 加速度値の取得
    gyr = getGyro()  # ジャイロ値の取得
    mag = getMag()  # 磁気値の取得
    # データの表示
    # ファイルへ書出し
    value = "%s,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f,%6.3f" % (
    date, acc[0], acc[1], acc[2], gyr[0], gyr[1], gyr[2], mag[0], mag[1], mag[2])  # 時間、xyz軸回りの加速度
    print(value)
    f_mpu9250.write(value + "\n")  # ファイルを出力
    
    
  gps_data = ser.readline()  #1行ごとに読み込み、処理を繰り返す
  if not gps_data:
    print("no data")
  #GGA GPSセンサの位置情報を知る
  #$GPGGA,UTC時刻,緯度,緯度の南北,経度,経度の東西,位置特定品質,使用衛星数,
  #水平精度低下率,海抜高さ,高さの単位,ジオイド高さ,高さの単位,DGPS,差動基準地点
  if (gps_data.startswith('$GPGGA')): #startswith:1行の先頭文字を検索する
    gpgga = (gps_data.split(",")) #split:1行をカンマで区切って変数にlist型で保存
    #緯度と経度の情報を、listからfloatに直す
    if gpgga[2]:
      lat_60,long_60,altitude = float(gpgga[2]),float(gpgga[4]),float(gpgga[9])
    else:
      lat_60,long_60,altitude = 0,0,0    #緯度の情報が無い
    #緯度と経度を60進法から10進法に変換、東経と北緯で計算
    if gpgga[3] == "W":  lat_60 *= -1
    if gpgga[5] == "S":  long_60 *= -1
    lat_10,long_10 = sixty_to_ten(lat_60/100),sixty_to_ten(long_60/100)
    #csv形式で出力する用のデータを変数にまとめて保存する(なければ０とする)
    alt_lat_long = "%3.2f,%5.6f,%5.6f" % (altitude,lat_10,long_10) if gpgga[9] else "0,0,0" #高度、緯度、経度
    print(alt_lat_long)
###############
  #GSA 特定タイプを見ることでGPSの通信状況を確認する
  #$GPGSA,UTC時刻,特定タイプ,衛星番号,精度低下率(位置、水平、垂直)
  #if (gps_data.startswith('$GPGSA')):  print gps_data, #特定タイプ(2D,3D等)を確認するために表示。3の時が良好。
###############
  #GSV 受信した衛星の位置等の情報を記録する
  #$GPGSV,UTC時刻,総センテンス数,このセンテンスの番号,総衛星数,
  #衛星番号,衛星仰角,衛星方位角,キャリア/ノイズ比,　を繰り返す
    if (gps_data.startswith('$GPGSV')):
        f = open('datagsv.csv','a')
    gpgsv = (gps_data.split(','))
    #衛星の個数を記録し、情報を追加する
    if (gpgsv[2] == '1'):
      num_sat = gpgsv[3]
      f.write(gpgsv[1] + gpgsv[3] + '\n')
    #それぞれの衛星の番号、仰角、方位角を追加する
    if (len(gpgsv) == 4):  num_sat = '0'
    elif (len(gpgsv) >= 8):
      gsv1 =  gpgsv[4] + gpgsv[5] + gpgsv[6]   #センテンス中一つ目の衛星
      f.write(gsv1 + '\n')
    elif (len(gpgsv) >= 12):
      gsv2 =  gpgsv[8] + gpgsv[9] + gpgsv[10]  #二つ目の衛星
      f.write(gsv2 + '\n')
    elif (len(gpgsv) >= 16):
      gsv3 =  gpgsv[12] + gpgsv[13] + gpgsv[14]#三つ目の衛星
      f.write(gsv3 + '\n')
    elif (len(gpgsv) == 20):
      gsv4 =  gpgsv[16] + gpgsv[17] + gpgsv[18]#四つ目の衛星
      f.write(gsv4 + '\n')
    f.close()
#############
  #ZDA NMEA出力における最後の行のため、時間を調べつつ一括ファイル出力する
  #$GPZDA,UTC時刻(hhmmss.mm),日,月,西暦,時,分,
  if (gps_data.startswith('$GPZDA')):
    gpzda = (gps_data.split(","))
    #GPSで取得したUTCの日付を保存する
    yyyymmddhhmmssff = datetime.datetime.strptime(gpzda[4] + '/' + gpzda[3] + '/' + gpzda[2] + ' ' + gpzda[1],"%Y/%m/%d %H%M%S.%f")
    time_and_number = "%s,%s" % (yyyymmddhhmmssff,num_sat)
    #ファイル名を書き換える
    #GGAのデータを標準出力、加えてcsvファイルに出力
    f = open(new_name,'a')
    f.write(time_and_number + ',' + alt_lat_long + '\n')
    print(time_and_number + ',' + alt_lat_long)
    f.close()
f_mpu9250.close()
