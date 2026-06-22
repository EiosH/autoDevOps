// minesweeper.js

class Minesweeper {
  constructor(rows, cols) {
    this.rows = rows;
    this.cols = cols;
    this.board = Array.from({ length: rows }, () => Array(cols).fill(0));
    this.revealed = Array.from({ length: rows }, () => Array(cols).fill(false));
  }

  initializeMines(mines) {
    const minePositions = new Set();
    while (minePositions.size < mines) {
      const row = Math.floor(Math.random() * this.rows);
      const col = Math.floor(Math.random() * this.cols);
      const index = row * this.cols + col;
      if (!minePositions.has(index)) {
        minePositions.add(index);
        this.board[row][col] = -1;
      }
    }
  }

  revealCell(row, col) {
    if (row < 0 || row >= this.rows || col < 0 || col >= this.cols || this.revealed[row][col]) return;

    this.revealed[row][col] = true;
    if (this.board[row][col] === -1) throw new Error('Boom!');

    const count = this.countAdjacentMines(row, col);
    if (count > 0) {
      this.board[row][col] = count;
    } else {
      this.revealSurroundingCells(row, col);
    }
  }

  revealSurroundingCells(row, col) {
    for (let r = Math.max(0, row - 1); r <= Math.min(this.rows - 1, row + 1); r++) {
      for (let c = Math.max(0, col - 1); c <= Math.min(this.cols - 1, col + 1); c++) {
        this.revealCell(r, c);
      }
    }
  }

  countAdjacentMines(row, col) {
    let count = 0;
    for (let r = Math.max(0, row - 1); r <= Math.min(this.rows - 1, row + 1); r++) {
      for (let c = Math.max(0, col - 1); c <= Math.min(this.cols - 1, col + 1); c++) {
        if (this.board[r][c] === -1) count++;
      }
    }
    return count;
  }
}

const minefield = new Minesweeper(10, 10);
minefield.initializeMines(10);
console.log(minefield);