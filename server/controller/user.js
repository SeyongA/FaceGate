const nodemailer = require('nodemailer');
const dotenv = require('dotenv');
dotenv.config();
const { User } = require('../models');
const bcrypt = require('bcrypt');
const jwt = require('jsonwebtoken');

const NNcheckFunc = async (req, res) => {
  try {
    const { nickName } = req.query;
    console.log(nickName);
    const find = await User.findOne({ where: { nickName } });
    console.log(find);

    if (find) {
      res.json({ result: false, message: '이미 존재하는 닉네임' });
    } else {
      res.json({ result: true, message: '사용 가능한 닉네임' });
    }
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, message: '서버오류' });
  }
};

const emailCheck = async (req, res) =>{
  try {
    const { email } = req.body;
    const find = await User.findOne({where : {email}})
    if(!find){
      res.json({result : true});
    } else{
      res.status(409).json({result : false});
    }
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, message: '서버오류' });
  }
}

const sendMail = async (req, res) => {
  try {
    const { email } = req.body;
    // console.log(process.env);

    const { email_service, GMAIL, GPASS } = process.env;

    const transporter = nodemailer.createTransport({
      service: email_service,
      auth: {
        user: GMAIL,
        pass: GPASS,
      },
    });

    const code = String(Math.floor(Math.random() * 1000000)).padStart(6, '0');
    const emailHtml =
      `<p>안녕하세요.</p>
        <p>해당 메일은 ` +
      email +
      `이 정확한 이메일 주소인지 확인하는 메일입니다.</p>
        <p>JMT 인증 코드는 <strong>[` +
      code +
      `]</strong> 입니다.</p>
        <p>코드는 3분 후 만료됩니다.</p>`;

    const mailOptions = {
      from: GMAIL,
      to: email,
      subject: 'JMT 회원가입 이메일 인증코드가 도착하였습니다.',
      html: emailHtml,
    };

    transporter.sendMail(mailOptions, (error, info) => {
      if (error) {
        console.log(error);
        res.json({ result: false, info });
      } else {
        console.log('Email Sent', info);
        res.json({ result: true, code });
      }
    });
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, message: '서버오류' });
  }
};

const signupFunc = async (req, res) => {
  try {
    const { email, password, nickName } = req.body;
    const find = await User.findOne({ where: { email } });
    // console.log(find);
    if (find) {
      res.json({ result: false, message: '이미 존재하는 계정' });
    } else {
      const pass = await bcrypt.hash(password, 10);
      const result = await User.create({ email, password: pass, nickName });
      console.log(result);
      res.json({ result: true, message: '아이디 생성완료' });
    }
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, message: '서버오류' });
  }
};

const loginFunc = async (req, res) => {
  try {
    const { email, password, check } = req.body;
    const find = await User.findOne({ where: { email } });
    if (find) {
      const pass = await bcrypt.compare(password, find.password);
      if (!find.isEnabled) {
        return res.json({ result: false, code: 201, message: '탈퇴한 계정입니다.' });
      }
      if (pass) {
        const { userId, email } = find.dataValues;
        const token = jwt.sign({ userId, email }, process.env.SECRET, { expiresIn: '10h' });
        const response = { token };
        res.json({ result: true, check, email, response, message: '토큰 로그인 성공' });
      } else {
        res.json({ result: false, code: 202, response: null, message: '비밀번호가 일치하지 않습니다.' });
      }
    } else {
      res.json({ result: false, code: 200, response: null, message: '존재하지 않는 아이디' });
    }
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, response: null, message: '서버오류' });
  }
};

const infoFunc = async (req, res) => {
  try {
    const { email } = req.userInfo;
    const find = await User.findOne({ where: { email } });
    console.log(find, '들어옴');

    const { nickName, profileImg, aboutMe } = find;
    const response = {
      email,
      nickName,
      profileImg,
      aboutMe,
    };
    res.json({ result: true, response });
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, message: '서버오류' });
  }
};

const updateFunc = async (req, res) => {
  try {
    const { email } = req.userInfo;
    const { password, nickName, profileImg, aboutMe } = req.body;
    const pass = await bcrypt.hash(password, 10);
    const find = await User.findOne({ where: { email } });
    if (find) {
      await User.update({ password: pass, nickName, profileImg, aboutMe }, { where: { email } });
    }
    res.json({ result: true, message: '프로필 수정 성공' });
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, message: '서버오류' });
  }
};

const deleteFunc = async (req, res) => {
  try {
    const { email } = req.userInfo;
    const { isEnabled } = req.body;
    console.log('==============' + isEnabled);

    const find = await User.findOne({ where: { email } });
    if (find) {
      await User.update({ isEnabled }, { where: { email } });
    }
    res.json({ reslut: true });
  } catch (error) {
    console.log(error);
    res.status(500).json({ result: false, message: '서버오류' });
  }
};

module.exports = { sendMail, emailCheck, NNcheckFunc, signupFunc, loginFunc, infoFunc, updateFunc, deleteFunc };
