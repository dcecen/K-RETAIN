import { useEffect, useState } from 'react'

export default function App() {
  const [etat, setEtat] = useState('connexion au serveur de calcul…')
  useEffect(() => {
    fetch('/api/sante')
      .then((r) => r.json())
      .then((d) => setEtat(`serveur de calcul : ${d.statut} (v${d.version})`))
      .catch(() => setEtat('serveur de calcul injoignable'))
  }, [])
  return (
    <main style={{ fontFamily: 'system-ui', padding: 24 }}>
      <h1>RetainWall</h1>
      <p>{etat}</p>
    </main>
  )
}
