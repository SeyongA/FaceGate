require('dotenv').config();
const express = require('express');
const db = require('./models');
const app = express();
const PORT = 8000;
const cors = require('cors');

app.use(cors());

app.set('view engine', 'ejs');

app.use(express.json());
app.use('/public', express.static(__dirname + '/public'));

//라우터
const pageRouter = require('./routes/page');
app.use('/', pageRouter);

const userRouter = require('./routes/user');
app.use('/api/user', userRouter);

// db.sequelize.sync({ force: false }).then(() => {
app.listen(PORT, () => {
  console.log(`http://localhost:${PORT}`);
});
// });
