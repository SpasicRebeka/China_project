import { spawn } from 'node:child_process'
import { join } from 'node:path'

const python = process.platform === 'win32'
  ? join('.venv', 'Scripts', 'python.exe')
  : join('.venv', 'bin', 'python')

const child = spawn(
  python,
  ['-m', 'uvicorn', 'app.main:app', '--app-dir', 'services/api', '--host', '127.0.0.1', '--port', '8000'],
  { stdio: 'inherit' },
)

for (const signal of ['SIGINT', 'SIGTERM']) {
  process.on(signal, () => child.kill(signal))
}

child.on('exit', (code) => process.exit(code ?? 0))

