import '@testing-library/jest-dom/vitest'
import { cleanup, configure } from '@testing-library/react'
import { afterEach } from 'vitest'

// O padrão de 1 segundo estoura quando a máquina está ocupada (por exemplo, no CI ou com outra suíte rodando).
configure({ asyncUtilTimeout: 5000 })

afterEach(() => {
  cleanup()
})
