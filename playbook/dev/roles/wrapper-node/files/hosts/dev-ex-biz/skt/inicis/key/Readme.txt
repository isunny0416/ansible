====================[실 상점 아이디 적용하는 방법]=====================

주의 : INIpayTest 폴더 아래 키파일은 상점에서 사용하시면 금전적인 손해를 유발할수 있습니다
	반드시 이니시스에서 보내드린 압축 키파일로 키세팅을 하시기 바랍니다	

1. INIpay/key 폴더 아래 발급 받으신 상점 아이디 (10자리)로 된 디렉토리를 만듭니다.
	ex) INIpay/key/MerchantID/
	
2. 이메일로 받으신 zip 파일을 key 디렉토리 아래에 풉니다.
	ex) INIpay/key/MerchantID/keypass.enc
								mcert.pem
								mpriv.pem
	
3. INIpay/sample/INIsecurepay.html 의 	테스트 아이디를 발급받으신 상점 아이디로 바꿉니다.
	ex)
	<input type=hidden name=mid value="INIpayTest">(변경전)
	<input type=hidden name=mid value="MerchantID">(변경후)
	
4. INIpay/sample/INIsecurepay.asp(php,jsp) 페이지에 키 패스워드 변경 합니다
	ex) asp : INIpay.SetField CLng(PInst), "admin", "1111" '키패스워드(상점아이디에 따라 변경)
		php : $inipay->SetField("admin", "1111"); // 키패스워드(상점아이디에 따라 변경)
		jsp : inipay.SetField("admin","1111"); // 키패스워드(상점아이디에 따라 변경)
