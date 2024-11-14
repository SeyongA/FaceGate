const { DataTypes } = require('sequelize');

const user = (seq) => {
  return seq.define('user', {
    userId: {
      type: DataTypes.INTEGER,
      primaryKey: true,
      autoIncrement: true,
    },
  });
};

module.exports = user;
