import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Navbar from './components/Navbar'
import HouseholdList from './pages/HouseholdList'
import HouseholdDetail from './pages/HouseholdDetail'
import Insights from './pages/Insights'
import Upload from './pages/Upload'
import ReviewQueue from './pages/ReviewQueue'
import ReviewDetail from './pages/ReviewDetail'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main style={{ minHeight: 'calc(100vh - var(--navbar-height))' }}>
        <Routes>
          <Route path="/" element={<Navigate to="/households" replace />} />
          <Route path="/households" element={<HouseholdList />} />
          <Route path="/households/:id" element={<HouseholdDetail />} />
          <Route path="/insights" element={<Insights />} />
          <Route path="/upload" element={<Upload />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/review/:id" element={<ReviewDetail />} />
          <Route path="*" element={<Navigate to="/households" replace />} />
        </Routes>
      </main>
    </BrowserRouter>
  )
}
