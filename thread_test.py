from wpi3_GPS import *
from wpi3_mpu9250_2 import *
import time
import threading

def GPS_thread():
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
    ##############################################################################
    while True:
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

def mpu_thread():
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
    # while True:
    for _i in range(TIMES):
        try:
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
            # 指定秒数の一時停止
            sleepTime = SAMPLING_TIME - (time.time() - now)
            if sleepTime < 0.0:
                continue
            time.sleep(sleepTime)
        except KeyboardInterrupt:
            break
    f_mpu9250.close()  # 書き込みファイルを閉じる

if __name__ == "__main__":
    thread_GPS = threading.Thread(target=GPS_thread)
    thread_mpu = threading.Thread(target=mpu_thread)
    thread_GPS.start()
    thread_mpu.start()

