'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'

export default function SimpleLoginPage() {
  const router = useRouter()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState('')

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault()

    console.log('=== SIMPLE LOGIN START ===')
    console.log('Email entered:', email)
    console.log('Password entered:', password)

    // Demo credentials
    const demos = [
      { email: 'demo@example.com', password: 'demo123', name: 'Demo User', role: 'demo' },
      { email: 'admin@example.com', password: 'admin123', name: 'Admin User', role: 'admin' },
    ]

    const found = demos.find(d => d.email === email && d.password === password)
    console.log('User found:', found)

    if (found) {
      console.log('✅ SUCCESS!')
      localStorage.setItem('access_token', 'demo_token_' + Date.now())
      localStorage.setItem('user', JSON.stringify({
        name: found.name,
        email: found.email,
        role: found.role
      }))

      setMessage('✅ SUCCESS! Redirecting...')

      setTimeout(() => {
        router.push('/dashboard')
      }, 1000)
    } else {
      console.log('❌ FAILED')
      setMessage('❌ Wrong credentials')
    }
  }

  return (
    <div style={{ padding: '50px', maxWidth: '400px', margin: '0 auto' }}>
      <h1>SIMPLE LOGIN TEST</h1>

      <form onSubmit={handleLogin}>
        <div style={{ marginBottom: '20px' }}>
          <label>Email:</label><br/>
          <input
            type="text"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            style={{ width: '100%', padding: '10px', fontSize: '16px' }}
          />
        </div>

        <div style={{ marginBottom: '20px' }}>
          <label>Password:</label><br/>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            style={{ width: '100%', padding: '10px', fontSize: '16px' }}
          />
        </div>

        <button
          type="submit"
          style={{
            width: '100%',
            padding: '15px',
            fontSize: '18px',
            backgroundColor: '#0070f3',
            color: 'white',
            border: 'none',
            cursor: 'pointer'
          }}
        >
          LOGIN
        </button>
      </form>

      {message && (
        <div style={{
          marginTop: '20px',
          padding: '15px',
          backgroundColor: message.includes('✅') ? '#d4edda' : '#f8d7da',
          border: '1px solid ' + (message.includes('✅') ? '#c3e6cb' : '#f5c6cb'),
          fontSize: '16px',
          fontWeight: 'bold'
        }}>
          {message}
        </div>
      )}

      <div style={{ marginTop: '30px', padding: '15px', backgroundColor: '#f0f0f0' }}>
        <h3>Test Credentials:</h3>
        <p><strong>demo@example.com</strong> / demo123</p>
        <p><strong>admin@example.com</strong> / admin123</p>
      </div>

      <div style={{ marginTop: '20px', color: '#666' }}>
        <p>Open browser console (F12) to see debug logs</p>
      </div>
    </div>
  )
}
