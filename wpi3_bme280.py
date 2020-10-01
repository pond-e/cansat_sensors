#!/usr/bin/python3 -u
# -*- coding: utf-8 -*-

############################################################
# Written by S.U @ Takada Laboratory on 2018.03.06
# 
# Environment:  Python 3.4.2
#               OS: Raspbian 8.0 (jessie)
#               on Raspberry Pi 3
# Used sensor: BME-280(Akiduki denshi)
#
# PythonからI2C をコントロールするためのライブラリ「wiringpi2」のインストール必要。
#    $ sudo pip install wiringpi2 
#
# データをファイルに書出すので「bme280_logs.csv」の空ファイルを準備する
# pi@raspberrypi ~ $ sudo touch bme280_logs.csv
# pi@raspberrypi ~ $ sudo chown  pi bme280_logs.csv
#データ計測時間は　SAMPLING_TIME x TIMES
############################################################

import sys              #sysモジュールの呼び出し
import wiringpi as wi   #wiringPiモジュールの呼び出し
import time             #timeライブラリの呼び出し
import datetime         #datetimeモジュールの呼び出し
import os

#データ計測時間は　SAMPLING_TIME x TIMES
SAMPLING_TIME = 0.1     #データ取得の時間間隔[sec]
TIMES = 100                   #データの計測回数

wi.wiringPiSetup()      #wiringPiの初期化
i2c = wi.I2C()          #i2cの初期化

i2c_address = 0x76 # #I2Cアドレス SDO=GND
#i2c_address = 0x77 # #I2Cアドレス SDO=VCC
bme280 = i2c.setup(i2c_address)            #i2cアドレス0x76番地をbme280として設定(アドレスは$sudo i2cdetect 1で見られる)

digT = []	#配列を準備
digP = []	#配列を準備
digH = []	#配列を準備

temp = 0
humi = 0
press = 0
t_fine = 0.0

# レジスタへの書き込み
def writeReg(reg_address, data):
	i2c.writeReg8(bme280,reg_address,data)

# キャリブレーションデータの取得
def get_calib_param():
	calib = []
	
	for i in range (0x88,0x88+24):
		calib.append(i2c.readReg8(bme280,i))
	calib.append(i2c.readReg8(bme280,0xA1))
	for i in range (0xE1,0xE1+7):
		calib.append(i2c.readReg8(bme280,i))

	digT.append((calib[1] << 8) | calib[0])
	digT.append((calib[3] << 8) | calib[2])
	digT.append((calib[5] << 8) | calib[4])
	digP.append((calib[7] << 8) | calib[6])
	digP.append((calib[9] << 8) | calib[8])
	digP.append((calib[11]<< 8) | calib[10])
	digP.append((calib[13]<< 8) | calib[12])
	digP.append((calib[15]<< 8) | calib[14])
	digP.append((calib[17]<< 8) | calib[16])
	digP.append((calib[19]<< 8) | calib[18])
	digP.append((calib[21]<< 8) | calib[20])
	digP.append((calib[23]<< 8) | calib[22])
	digH.append( calib[24] )
	digH.append((calib[26]<< 8) | calib[25])
	digH.append( calib[27] )
	digH.append((calib[28]<< 4) | (0x0F & calib[29]))
	digH.append((calib[30]<< 4) | ((calib[29] >> 4) & 0x0F))
	digH.append( calib[31] )
	
	for i in range(1,2):
		if digT[i] & 0x8000:
			digT[i] = (-digT[i] ^ 0xFFFF) + 1

	for i in range(1,8):
		if digP[i] & 0x8000:
			digP[i] = (-digP[i] ^ 0xFFFF) + 1

	for i in range(0,6):
		if digH[i] & 0x8000:
			digH[i] = (-digH[i] ^ 0xFFFF) + 1  

# データの取得
def readData():
	data = []
	global temp
	global humi
	global press
	for i in range (0xF7, 0xF7+8):
		data.append(i2c.readReg8(bme280,i))
	pres_raw = (data[0] << 12) | (data[1] << 4) | (data[2] >> 4)
	temp_raw = (data[3] << 12) | (data[4] << 4) | (data[5] >> 4)
	hum_raw  = (data[6] << 8)  |  data[7]
	
	temp = compensate_T(temp_raw)
	press = compensate_P(pres_raw)
	humi = compensate_H(hum_raw)

# 気圧データを取得する
def compensate_P(adc_P):
	global  t_fine
	pressure = 0.0
	
	v1 = (t_fine / 2.0) - 64000.0
	v2 = (((v1 / 4.0) * (v1 / 4.0)) / 2048) * digP[5]
	v2 = v2 + ((v1 * digP[4]) * 2.0)
	v2 = (v2 / 4.0) + (digP[3] * 65536.0)
	v1 = (((digP[2] * (((v1 / 4.0) * (v1 / 4.0)) / 8192)) / 8)  + ((digP[1] * v1) / 2.0)) / 262144
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
	
	print("pressure : %7.2f hPa" % (pressure/100))
	return pressure/100

# 温度データを取得する
def compensate_T(adc_T):
	global t_fine
	v1 = (adc_T / 16384.0 - digT[0] / 1024.0) * digT[1]
	v2 = (adc_T / 131072.0 - digT[0] / 8192.0) * (adc_T / 131072.0 - digT[0] / 8192.0) * digT[2]
	t_fine = v1 + v2
	temperature = t_fine / 5120.0
	print("temp : %-6.2f ℃" % (temperature)) 
	return temperature

# 湿度データを取得する
def compensate_H(adc_H):
	global t_fine
	var_h = t_fine - 76800.0
	if var_h != 0:
		var_h = (adc_H - (digH[3] * 64.0 + digH[4]/16384.0 * var_h)) * (digH[1] / 65536.0 * (1.0 + digH[5] / 67108864.0 * var_h * (1.0 + digH[2] / 67108864.0 * var_h)))
	else:
		return 0
	var_h = var_h * (1.0 - digH[0] * var_h / 524288.0)
	if var_h > 100.0:
		var_h = 100.0
	elif var_h < 0.0:
		var_h = 0.0
	print("hum : %6.2f ％" % (var_h))
	return var_h

# 設定
def setup():
	#osrs_t[2:0] 温度オーバーサンプリング設定
	#スキップ(output set to 0x80000)=0 オーバーサンプリング×1=1 オーバーサンプリング×2= 2 オーバーサンプリング×4= 3 オーバーサンプリング ×8=4 オーバーサンプリング ×16=5
	osrs_t = 1			#温度オーバーサンプリング x 1
	#osrs_p[2:0] 気圧オーバーサンプリング 設定
	#スキップ(output set to 0x80000)=0 オーバーサンプリング ×1=1 オーバーサンプリング ×2=2	オーバーサンプリング ×4=3 オーバーサンプリング ×8=4 オーバーサンプリング ×16=5
	osrs_p = 3			#気圧オーバーサンプリング x 4
	#osrs_h[2:0] 湿度オーバーサンプリング settings
	#スキップ(output set to 0x80000)=0 オーバーサンプリング ×1=1 オーバーサンプリング ×2=2	オーバーサンプリング ×4=3 オーバーサンプリング ×8=4 オーバーサンプリング ×16=5
	osrs_h = 0			#湿度オーバーサンプリング Skipped
	mode   = 3			#ノーマルモード (Sleep mode:0 Forced mode:1 Normal mode:3)
	#t_sb[2:0] tstandby [ms]
	# 0= 0.5[ms] 1= 62.5[ms] 2= 125[ms] 3= 250[ms] 4= 500[ms] 5= 1000[ms] 6= 10[ms] 7= 20[ms]
	t_sb   = 0			#Tstandby 0.5ms
	#filter[2:0] Filter coefficient
	#0= Filter off 1=coefficient2 2=coefficient4 3=coefficient8 4=coefficient 16
	filter = 4			#Filter coefficient 16
	spi3w_en = 0			#3-wire SPI Disable

	ctrl_meas_reg = (osrs_t << 5) | (osrs_p << 2) | mode
	config_reg    = (t_sb << 5) | (filter << 2) | spi3w_en
	ctrl_hum_reg  = osrs_h

	writeReg(0xF2,ctrl_hum_reg)
	writeReg(0xF4,ctrl_meas_reg)
	writeReg(0xF5,config_reg)


setup()
get_calib_param()

#ファイルへ書出し準備
now = datetime.datetime.now()
#現在時刻を織り込んだファイル名を生成
fmt_name = "/home/pi/data/bme280_logs_{0:%Y%m%d-%H%M%S}.csv".format(now)
f_bme280= open(fmt_name, 'w')    #書き込みファイル
#f_bme280= open('bme280_logs.csv', 'w')    #書き込みファイル
value="yyyy-mm-dd hh:mm:ss.mmmmmm, T[℃],H[%],P[hPa]"   #header行への書き込み内容
f_bme280.write(value+"\n")   #header行をファイル出力

if __name__ == '__main__':
	#while True:
	for _i in range(TIMES):
		try:
			date = datetime.datetime.now()  #now()メソッドで現在日付・時刻のdatetime型データの変数を取得 世界時：UTCnow
			now     = time.time()     #現在時刻の取得
			readData()
			#ファイルへ書出し
			value= "%s,%6.2f,%6.2f,%7.2f" % (date, temp,humi,press)      #時間、温度、湿度、気圧
			f_bme280 .write(value + "\n")       #ファイルを出力
			#指定秒数の一時停止
			sleepTime       = SAMPLING_TIME - (time.time() - now)
			if sleepTime < 0.0:
				continue
			time.sleep(sleepTime)
		except KeyboardInterrupt:
			pass

	f_bme280 .close()                       #書き込みファイルを閉じる



