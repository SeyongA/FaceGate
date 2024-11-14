const express = require('express');
const { main } = require('../controller/page');
const router = express.Router();

router.get('/', main);

module.exports = router;
