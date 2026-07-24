import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import Layout from './components/Layout'
import Echo from './pages/Echo'
import Inbox from './pages/Inbox'
import Prep from './pages/Prep'
import WordBank from './pages/WordBank'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Inbox />} />
          <Route path="prep/:sourceId" element={<Prep />} />
          <Route path="echo/:sourceId" element={<Echo />} />
          <Route path="bank" element={<WordBank />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}
