require('dotenv').config();
const express = require('express');
const { sendMail } = require('../controller/user');

const router = express.Router();

router.post('/mail', sendMail); //세용

module.exports = router;
