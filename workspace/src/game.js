// src/Game.js
import React, { useState } from 'react';

const Game = () => {
  const [gameOver, setGameOver] = useState(false);

  return (
    <div>
      {!gameOver ? (
        <button onClick={() => setGameOver(true)}>Start Game</button>
      ) : null}
      {gameOver && <p>Game Over</p>}
      <div onKeyDown={(e) => e.key === ' ' && setGameOver(false)} tabIndex=