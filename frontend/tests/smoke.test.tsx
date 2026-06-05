import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AuthProvider } from '../src/hooks/useAuth'
import App from '../src/App'

describe('F0 scaffold smoke', () => {
  it('renders without crashing', () => {
    render(<App />)
    // App renders without throwing
  })

  it('auth provider wraps children', () => {
    render(
      <MemoryRouter>
        <AuthProvider>
          <div data-testid="child">hello</div>
        </AuthProvider>
      </MemoryRouter>
    )
    expect(screen.getByTestId('child')).toBeInTheDocument()
  })
})
