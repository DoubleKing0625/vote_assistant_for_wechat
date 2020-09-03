import time
import json
import base64
import random
import string
import uuid

import requests
import datetime
import urllib3
import re
from PIL import Image
from cnocr import CnOcr
from collections import defaultdict
from Crypto.Cipher import AES, DES
from Crypto.Util.Padding import pad
from urllib import parse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def request_token():
    ouid = str(33) + str(random.randint(0, 999999))
    headers_info = {
        "uid": ouid,
        "token": ""
    }
    print("headers_info: {}".format(headers_info))
    headers_data1 = parse.quote(json.dumps(headers_info))
    headers_data2 = parse.quote(headers_data1)
    # print(headers_data2)

    ########################## step1: get D5O_uphit_1903098 ########################################
    headers = {
        "Cookie": "D5O_openinfos={};D5O_advice_brandid_0=1903098;D5O_back_sid_0=10a1d7ac79d49544".format(headers_data2),
        # "cookie": "D5O_openinfos={};D5O_uphit_1903098=562665;D5O_advice_brandid_0=1903098;D5O_back_sid_0=10a1d7ac79d49544".format(headers_data2),
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) MicroMessenger/6.8.0(0x16080000) MacWechat/2.4.2(0x12040212) NetType/WIFI WindowsWechat"
    }
    token_res = requests.get("https://h5.zhiyyuan.cn/m.php?v=10a1d7ac79d49544", verify=False, headers=headers)
    # print(token_res.text)
    cookies = requests.utils.dict_from_cookiejar(token_res.cookies)
    uphit = cookies['D5O_uphit_1903098']
    print("uphit: {}".format(uphit))

    ########################## step2: get token ########################################
    headers2 = {
        "Accept": "*/*",
        "Host": "h5.zhiyyuan.cn",
        "Cookie": "D5O_openinfos={};D5O_uphit_1903098={};D5O_advice_brandid_0=1903098;D5O_back_sid_0=10a1d7ac79d49544".format(
            headers_data2, uphit),
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_6) AppleWebKit/605.1.15 (KHTML, like Gecko) MicroMessenger/6.8.0(0x16080000) MacWechat/2.4.2(0x12040212) NetType/WIFI WindowsWechat"
    }
    code = ''.join(str(uuid.uuid1()).split("-"))  # 生成将随机字符串 与 uuid拼接
    print("code: {}".format(code))
    payload = {
        "jumpnum": 1,
        "weixincheck": 1,
        "dtime": int(time.time()),
        "code": code,
        "state": "https://h5.zhiyyuan.cn/m.php?v=10a1d7ac79d49544"
    }
    print(payload)
    print(headers2)
    session = requests.Session()
    token_res = session.get("https://h5.zhiyyuan.cn/m.php", params=payload, verify=False, headers=headers2)
    prog = re.compile(r"var tokenVal='(.*)'")
    print('==========tokenVal===========')
    token = prog.search(token_res.text).group(1)
    print("tokenVal: {}".format(token))
    return ouid, token


def try_vote_once(ocr):
    ########################## step1: get verify img ########################################
    headers = {
        "Host": "v.tiantianvote.com",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        "Origin": "https://h5.zhiyyuan.cn",
        "Referer": "https://h5.zhiyyuan.cn/m.php?v=10a1d7ac79d49544?xcb808wy&id=157&sign=friend&id=110&sign=circle&id=125&sign=circle&id=125&sign=circle&id=106&sign=friend",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_13_1) AppleWebKit/604.3.5 (KHTML, like Gecko) MicroMessenger/6.8.0(0x16080000) MacWechat/2.4.2(0x12040211) NetType/WIFI WindowsWechat",
    }
    randomNum = 19030984501745 * 1000000 + random.randint(0, 999999)
    params = {
        "rnd": randomNum,  # 538645,随机数规则：19030984501745 + 后六位随机
        "type": 2,  # 固定
        "id": 4501745  # 固定
    }
    verifyCodeRes = requests.get(
        "https://v.tiantianvote.com/api/c2/captchas.png.php",
        headers=headers,
        params=params, verify=False)
    with open("verify.jpg", "wb+") as f:
        f.write(verifyCodeRes.content)

    ########################## step2: ocr verify img ########################################
    im = Image.open('verify.jpg')

    ##把彩色图像转化为灰度图像。RBG转化到HSI彩色空间，采用I分量
    gray = im.convert('L')

    ##获取二值化阈值，使用出现次数最多的像素值
    def _get_threshold(image):
        pixel_dict = defaultdict(int)
        # 像素及该像素出现次数的字典
        rows, cols = image.size
        for i in range(rows):
            for j in range(cols):
                pixel = image.getpixel((i, j))
                pixel_dict[pixel] += 1

        count_max = max(pixel_dict.values())  # 获取像素出现出多的次数
        pixel_dict_reverse = {v: k for k, v in pixel_dict.items()}
        threshold = pixel_dict_reverse[count_max]  # 获取出现次数最多的像素点
        return threshold

    threshold = _get_threshold(gray)

    ##根据阈值二值化
    def _get_bin_table(threshold):
        # 获取灰度转二值的映射table
        table = []
        for i in range(256):
            rate = 0.1  # 在threshold的适当范围内进行处理
            if threshold * (1 - rate) <= i <= threshold * (1 + rate):
                table.append(1)
            else:
                table.append(0)
        return table

    table = _get_bin_table(threshold)
    out = gray.point(table, '1')

    ## 去掉二值化处理后的图片中的噪声点
    def _cut_noise(image):
        rows, cols = image.size  # 图片的宽度和高度
        change_pos = []  # 记录噪声点位置

        # 遍历图片中的每个点，除掉边缘
        for i in range(1, rows - 1):
            for j in range(1, cols - 1):
                # pixel_set用来记录该店附近的黑色像素的数量
                pixel_set = []
                # 取该点的邻域为以该点为中心的九宫格
                for m in range(i - 1, i + 2):
                    for n in range(j - 1, j + 2):
                        if image.getpixel((m, n)) != 1:  # 1为白色,0位黑色
                            pixel_set.append(image.getpixel((m, n)))

                # 如果该位置的九宫内的黑色数量小于等于4，则判断为噪声
                if len(pixel_set) <= 4:
                    change_pos.append((i, j))

        # 对相应位置进行像素修改，将噪声处的像素置为1（白色）
        for pos in change_pos:
            image.putpixel(pos, 1)

        return image  # 返回修改后的图片

    out = _cut_noise(out)

    ##保存图片
    out.save('processed_verify.jpg')

    ##调用ocr模型分辨验证码
    res = ocr.ocr_for_single_line('processed_verify.jpg')

    ##检查ocr结果
    if len(res) != 4:
        return -1
    for r in res:
        if '0' > r or '9' < r:
            return -1
    res = "".join(res)
    print("verify code: {}".format(res))

    ########################## step3: encode verify code ########################################
    def _aes_cipher(key, aes_str):
        # 使用key,选择加密方式
        aes = DES.new(key.encode('utf-8'), DES.MODE_ECB)
        pad_pkcs7 = pad(aes_str.encode('utf-8'), DES.block_size, style='pkcs7')  # 选择pkcs7补全
        encrypt_aes = aes.encrypt(pad_pkcs7)
        # 加密结果
        encrypted_text = str(base64.encodebytes(encrypt_aes), encoding='utf-8').strip()  # 解码
        return encrypted_text

    key = "cyLdMCXU"
    encryption_res = _aes_cipher(key, res)
    print("encry verify code: {}".format(encryption_res))

    ########################## step4: vote ########################################
    # 获取token
    ouid, token = request_token()

    # 检查验证码
    # data_check = {
    #     "captcha": encryption_res,
    #     "rnd": randomNum,
    #     "type": "2",
    #     "id": "4501745"
    # }
    # check_res = requests.post("https://v.tiantianvote.com/api/c2/captchas.check1.php", data=data_check, headers=headers, verify=False)
    # print("request response message: {}".format(json.loads(check_res.content)))
    # print("request response message: {}".format(eval(check_res.text[1:])['msg']))

    data = {
        "brandid": "1903098",  # 固定
        "itemid": "4501745",  # 固定，与1中id保持统一
        "yqm": encryption_res,  # 3中获取的加密字符串
        "rnd": randomNum,  # 与1中rnd保持统一
        "token": token,  # 为空字符串
        "ouid": ouid,  # 固定
        "sid": "10a1d7ac79d49544"  # 微信的唯一id，不知是否是必填，到时候可以测一下，是否不传可行
    }
    voteRes = requests.post("https://v.tiantianvote.com/v.php", headers=headers, data=data, verify=False)
    print("request response message: {}".format(json.loads(voteRes.content)))
    # print("request response message: {}".format(eval(voteRes.text[1:])['msg']))
    rtn = eval(voteRes.text[1:])['msg']
    return rtn


def main():
    rtn = -1
    ocr = CnOcr(cand_alphabet=string.digits)
    print('============开始投票=============')
    while True:
        start_time = datetime.datetime.strptime(str(datetime.datetime.now().date()) + '7:00', '%Y-%m-%d%H:%M')
        end_time = datetime.datetime.strptime(str(datetime.datetime.now().date()) + '23:50', '%Y-%m-%d%H:%M')
        # 当前时间
        n_time = datetime.datetime.now()
        if n_time > start_time and n_time < end_time:
            if rtn in ["success", "您已经进行过支持了！每位用户每半小时可支持一次"]:
                # 上一次尝试成功了， 需要休眠30分钟
                time.sleep(30 * 60)
            rtn = try_vote_once(ocr)
            time.sleep(2)


if __name__ == '__main__':
    # main()
    request_token()
