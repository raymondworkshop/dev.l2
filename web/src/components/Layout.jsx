import { NavLink, Outlet } from 'react-router-dom'

export default function Layout() {
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
      <main className="main">
        <Outlet />
      </main>
    </div>
  )
}
