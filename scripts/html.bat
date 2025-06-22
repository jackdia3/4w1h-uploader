@echo off
setlocal enabledelayedexpansion

cd /d %~dp0
cd ..

@REM set ITEM1=hotsand
@REM set ITEM2=flyer
@REM set ITEM3=pan
@REM set ITEM4=stove-supporter
@REM set ITEM5=plate
@REM set ITEM6=pasta-pan
@REM set ITEM7=flat-kettle
set ITEM8=turner
set ITEM9=ladle
@REM set ITEM10=rice
@REM set ITEM11=gyouza-pan

for %%I in (5 6 7 8 9 10) do (
    call set ITEM=!ITEM%%I!
    echo ==============================
    echo 處理項目：!ITEM!
    python scripts/generate_html.py !ITEM!
)
4w1h_001R
　日本燕三條 4w1h • 半半熱壓吐司夾 Hot-Sand Solo｜一片吐司的份量，剛剛好，不多也不膩
4w1h_002
　日本燕三條 4w1h • 方方炸物鍋 Compact Fryer｜省油省時省力的料理好幫手
4w1h_003
　日本燕三條 4w1h • 菱形平底鍋 Diamond Frying Pan｜一鍋多用的萬能設計
4w1h_004
　日本燕三條 4w1h • 瓦斯爐支架 Stove Supporter｜穩固防滑，適用各式鍋具
4w1h_005
　日本燕三條 4w1h • 角型解凍盤 Plate｜快速解凍，保留食材鮮度
4w1h_006
　日本燕三條 4w1h • 義大利麵鍋 Pasta Pan｜一鍋多用，煮麵煮湯都方便
4w1h_007
　日本燕三條 4w1h • 直火專用快煮壺 Flat Kettle｜輕巧省空間，露營居家都適用
4w1h_008
　日本燕三條 4w1h • 多功能鍋鏟 Turner｜翻炒盛裝一把搞定
4w1h_009
　日本燕三條 4w1h • 多用途湯杓 Ladle｜深淺適中，盛湯盛料都合適
4w1h_010
　日本燕三條 4w1h • 多功能飯勺 Rice Paddle｜不沾好握，盛飯更輕鬆
4w1h_011
　日本燕三條 4w1h • 餃子鍋 Gyouza Pan｜專為煎餃設計，受熱均勻不沾黏
pause