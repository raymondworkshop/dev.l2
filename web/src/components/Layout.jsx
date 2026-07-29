import { useEffect, useState } from 'react'
import { NavLink, Outlet } from 'react-router-dom'

function isIosSafari() {
  if (typeof navigator === 'undefined') return false
  const ua = navigator.userAgent || ''
  const iOS = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)
  const standalone = window.navigator.standalone === true
  const safari = /Safari/.test(ua) && !/CriOS|FxiOS|EdgiOS|OPiOS/.test(ua)
  return iOS && safari && !standalone
}

export default function Layout() {
  const [showInstall, setShowInstall] = useState(false)

  useEffect(() => {
    try {
      if (sessionStorage.getItem('echo-hide-a2hs') === '1') return
    } catch {
      /* ignore */
    }
    setShowInstall(isIosSafari())
  }, [])

  function dismissInstall() {
    setShowInstall(false)
    try {
      sessionStorage.setItem('echo-hide-a2hs', '1')
    } catch {
      /* ignore */
    }
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <NavLink to="/" className="brand">
          Echo
        </NavLink>
        <nav className="nav">
          <NavLink to="/" end>
            Inbox
          </NavLink>
          <NavLink to="/bank">Word</NavLink>
        </nav>
      </header>
      {showInstall ? (
        <div className="a2hs-hint" role="status">
          <p>
            Add to Home Screen: Share <span aria-hidden="true">□↑</span> → <strong>Add to Home Screen</strong>
          </p>
          <button type="button" className="a2hs-dismiss" onClick={dismissInstall} aria-label="Dismiss">
            ×
          </button>
        </div>
      ) : null}
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
