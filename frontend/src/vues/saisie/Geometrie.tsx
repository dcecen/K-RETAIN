import { useState, type ReactNode } from 'react'
import { api, messageErreur } from '../../lib/api'
import { confirmer, informer } from '../../lib/dialogue'
import { uniteCote } from '../../lib/format'
import { aretesContour, lireGeometrie } from '../../lib/geometriePlan'
import { IconeCorbeille, IconePlus } from '../../lib/icones'
import type { Chemin, Modele } from '../../lib/scriptDoc'
import { Case, Champ, ChampPaire, Choix, ErreursBloc, Th } from './champs'
import { COLS_OBJET, LIBELLES_METHODE_OBJET } from './cles'
import { doc, type Ctx } from './outils'
import { PlanSvg } from './PlanSvg'

/** Cases à cocher écrivant toujours une liste (clé `cotes` : liste de noms de côtés ou de numéros d'arête). */
function CasesCotes({ ctx, chemin, valeur, options }: { ctx: Ctx; chemin: Chemin; valeur: unknown; options: string[] }) {
  const actuels: string[] = Array.isArray(valeur) ? valeur.map(String) : valeur === undefined || valeur === null ? [] : [String(valeur)]
  const basculer = (o: string) => {
    const l = actuels.includes(o) ? actuels.filter((x) => x !== o) : [...actuels, o]
    ctx.actions.fixer(chemin, l.length === 0 ? '' : l.map((x) => (/^\d+$/.test(x) ? Number(x) : x)))
  }
  if (!options.length) return <span className="note">aucun côté</span>
  return (
    <div className="cases-choix" title="vide = tous les côtés">
      {options.map((o) => <label key={o} className={`case-choix ${actuels.includes(o) ? 'actif' : ''}`}><input type="checkbox" checked={actuels.includes(o)} onChange={() => basculer(o)} /> {o}</label>)}
    </div>
  )
}

function Bloc({ titre, enfants, droite }: { titre: string; enfants: ReactNode; droite?: ReactNode }) {
  return <div className="bloc"><div className="bloc-titre">{titre}<span className="espace" />{droite}</div>{enfants}</div>
}

export function Geometrie({ ctx }: { ctx: Ctx }) {
  const m: Modele = ctx.modele ?? {}
  const unite = uniteCote(m)
  const g = lireGeometrie(m)
  const geo: Modele = m.geometrie ?? {}
  const aretes = aretesContour(g.contour, g.ferme, g.cotes)
  const nomsCotes = aretes.map((a) => a.nom ?? String(a.k))
  const appuis = Object.keys(m.appuis ?? {})
  const surcharges: string[] = (Array.isArray(m.surcharges) ? m.surcharges : []).map((s: Modele, i: number) => String(s?.nom ?? `S${i + 1}`))
  const phases: Modele[] = Array.isArray(m.phases) ? m.phases : []
  const [survol, setSurvol] = useState<string | null>(null)
  const [conversion, setConversion] = useState(false)
  const nouvelleForme = !!m.geometrie

  const convertir = async () => {
    if (!(await confirmer(`Réécrire la géométrie dans le bloc geometrie et retirer la forme ancienne (${g.anciens.join(', ')}) du script ?`, { titre: 'Convertir la géométrie', ok: 'Convertir' }))) return
    setConversion(true)
    try {
      const r = await api.geometrieNormaliser(ctx.texte ?? '')
      for (const chemin of r.anciens) ctx.actions.supprimer(chemin.split('.'))
      ctx.actions.fixer(['geometrie'], r.bloc)
    } catch (e) {
      void informer(`Conversion impossible : ${messageErreur(e)}`)
    } finally {
      setConversion(false)
    }
  }

  const ajouterSommet = () => {
    const c = g.contour
    const dernier = c[c.length - 1] ?? [0, 0]
    ctx.actions.ajouter(['geometrie', 'ouvrages', 'contour'], [Math.round((dernier[0] + 10) * 100) / 100, dernier[1]])
  }
  const nomCoteDe = (k: number) => aretes[k]?.nom ?? ''
  const renommerCote = (k: number, nom: string) => {
    const ancien = nomCoteDe(k)
    if (ancien) ctx.actions.supprimer(['geometrie', 'ouvrages', 'cotes', ancien])
    if (nom.trim()) ctx.actions.ajouterCle(['geometrie', 'ouvrages', 'cotes'], nom.trim(), k)
  }
  const objets: Modele[] = Array.isArray(geo.fouille?.objets) ? geo.fouille.objets : []
  const zonesFond: Modele[] = Array.isArray(geo.fouille?.zones) ? geo.fouille.zones : []
  const zonesTerrain: Modele[] = Array.isArray(geo.terrain?.zones) ? geo.terrain.zones : []
  const positions: Modele[] = Array.isArray(geo.surcharges) ? geo.surcharges : []
  const appuisPlan: Modele[] = Array.isArray(geo.ouvrages?.appuis) ? geo.ouvrages.appuis : []
  const suppr = (chemin: Chemin, libelle: string) => void confirmer(`Supprimer ${libelle} du script ?`, { ok: 'Supprimer' }).then((ok) => { if (ok) ctx.actions.supprimer(chemin) })

  return (
    <div className="saisie">
      <p className="aide">La géométrie décrit le modèle 2D ou 3D : tracé de la paroi en plan et côtés nommés, terrain côté terre, fouille (zones de fond,
        risbermes, talus, gradins avec leur étendue le long des côtés), positions des surcharges et des appuis en plan. Le calcul 2D crée une
        coupe par tronçon homogène ; le pseudo-3D rapporte chaque donnée aux lignes verticales qu'elle concerne. Cotes en {unite}, x et y en m.</p>
      {!nouvelleForme && (
        <div className="alerte orange" style={{ marginBottom: 12 }}>
          {g.anciens.length
            ? <>Ce script décrit sa géométrie sous la forme ancienne ({g.anciens.join(', ')}), toujours lue et convertie automatiquement. Pour la modifier ici, convertissez-la vers le bloc <span className="mono">geometrie</span>. </>
            : <>Ce script n'a pas encore de géométrie en plan (calcul 2D sur une coupe). Créez le bloc <span className="mono">geometrie</span> pour positionner les ouvrages. </>}
          <button className="btn" disabled={conversion} onClick={() => (g.anciens.length ? void convertir() : ctx.actions.fixer(['geometrie'], { ouvrages: { contour: [[0, 0], [20, 0], [20, 12], [0, 12]], cotes: { sud: 0, est: 1, nord: 2, ouest: 3 } } }))}>
            {g.anciens.length ? 'Convertir vers le bloc geometrie' : 'Créer un contour 20 × 12 m'}
          </button>
        </div>
      )}
      <div className="geometrie-colonnes">
        <div>
          <Bloc titre="Plan" enfants={<div style={{ padding: 8 }}><PlanSvg g={g} surbrillance={survol} /></div>} />
        </div>
        <div style={{ minWidth: 0 }}>
          <Bloc titre="Ouvrages : contour de la paroi en plan" droite={nouvelleForme && <label className="doux" style={{ fontWeight: 400 }}><Case ctx={ctx} chemin={['geometrie', 'ouvrages', 'ferme']} valeur={geo.ouvrages?.ferme ?? true} bloc="OuvragesGeo" cle="ferme" libelle="Contour fermé" /> contour fermé</label>}
            enfants={(
              <table className="tableau compact">
                <thead><tr><Th t="Sommet" /><Th t="x" u="m" /><Th t="y" u="m" /><Th t="Côté qui part de ce sommet" /><Th t="Longueur" u="m" /><th /></tr></thead>
                <tbody>
                  {g.contour.map(([x, y], i) => {
                    const a = aretes[i]
                    return (
                      <tr key={i} onMouseEnter={() => setSurvol(`cote:${i}`)} onMouseLeave={() => setSurvol(null)}>
                        <td className="mono">{i}</td>
                        <td>{nouvelleForme ? <Champ ctx={ctx} chemin={['geometrie', 'ouvrages', 'contour', i, 0]} valeur={x} bloc="OuvragesGeo" cle="contour" libelle={`Sommet ${i}, x`} /> : x}</td>
                        <td>{nouvelleForme ? <Champ ctx={ctx} chemin={['geometrie', 'ouvrages', 'contour', i, 1]} valeur={y} bloc="OuvragesGeo" cle="contour" libelle={`Sommet ${i}, y`} /> : y}</td>
                        <td>{a ? (nouvelleForme
                          ? <input className="champ" defaultValue={a.nom ?? ''} placeholder={`côté ${i}`} key={a.nom ?? `k${i}`} title={doc(ctx.schema, 'OuvragesGeo', 'cotes')}
                            onBlur={(e) => { if (e.target.value.trim() !== (a.nom ?? '')) renommerCote(i, e.target.value) }} onKeyDown={(e) => { if (e.key === 'Enter') (e.target as HTMLInputElement).blur() }} />
                          : (a.nom ?? `côté ${i}`)) : <span className="faible">—</span>}</td>
                        <td className="num doux">{a ? a.L.toFixed(2) : '—'}</td>
                        <td>{nouvelleForme && <button className="btn icone discret" title="Supprimer ce sommet" disabled={g.contour.length <= 3} onClick={() => suppr(['geometrie', 'ouvrages', 'contour', i], `le sommet ${i}`)}><IconeCorbeille taille={14} /></button>}</td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )} />
          {nouvelleForme && <button className="btn" onClick={ajouterSommet} style={{ marginBottom: 16 }}><IconePlus /> Ajouter un sommet</button>}

          <Bloc titre="Appuis en plan (vide : placement automatique à l'espacement)" enfants={(
            <table className="tableau compact">
              <thead><tr><Th t="Appui" /><Th t="Départ x ; y" u="m" /><Th t="Arrivée x ; y" u="m" /><th /></tr></thead>
              <tbody>
                {appuisPlan.map((ap, i) => (
                  <tr key={i} onMouseEnter={() => setSurvol(`appui:${ap?.appui}`)} onMouseLeave={() => setSurvol(null)}>
                    <td><Choix ctx={ctx} chemin={['geometrie', 'ouvrages', 'appuis', i, 'appui']} valeur={ap?.appui} options={appuis} bloc="AppuiPlan" cle="appui" libelle="Appui" /></td>
                    <td><ChampPaire ctx={ctx} chemin={['geometrie', 'ouvrages', 'appuis', i, 'de']} valeur={ap?.de} bloc="AppuiPlan" cle="de" libelle="Point de départ" /></td>
                    <td><ChampPaire ctx={ctx} chemin={['geometrie', 'ouvrages', 'appuis', i, 'a']} valeur={ap?.a} bloc="AppuiPlan" cle="a" libelle="Point d'arrivée" /></td>
                    <td><button className="btn icone discret" title="Supprimer" onClick={() => suppr(['geometrie', 'ouvrages', 'appuis', i], `la position de l'appui ${ap?.appui}`)}><IconeCorbeille taille={14} /></button></td>
                  </tr>))}
                {appuisPlan.length === 0 && <tr><td colSpan={4} className="doux">Appuis répartis automatiquement à leur espacement depuis le côté le plus long.</td></tr>}
              </tbody>
            </table>
          )} />
          {nouvelleForme && appuis.length > 0 && <button className="btn" style={{ marginBottom: 16 }} onClick={() => ctx.actions.ajouter(['geometrie', 'ouvrages', 'appuis'], { appui: appuis[0], de: [g.contour[0]?.[0] ?? 0, g.contour[0]?.[1] ?? 0], a: [g.contour[2]?.[0] ?? 0, g.contour[2]?.[1] ?? 0] })}><IconePlus /> Ajouter une position d'appui</button>}

          <Bloc titre="Terrain côté terre" enfants={(
            <>
              <div className="grille-form" style={{ padding: '6px 10px' }}>
                <label>Cote du terrain ({unite}){nouvelleForme ? <Champ ctx={ctx} chemin={['geometrie', 'terrain', 'cote']} valeur={geo.terrain?.cote} placeholder="toit de la 1re couche" bloc="TerrainGeo" cle="cote" large libelle="Cote du terrain côté terre" /> : <span className="doux"> {m.terrain?.amont ?? 'toit de la 1re couche'}</span>}</label>
              </div>
              <table className="tableau compact">
                <thead><tr><Th t="Zone" /><Th t="Côtés" titre="vide = tous" /><Th t="De" u="m" /><Th t="À" u="m" /><Th t="Cote" u={unite} /><Th t="Pente β" u="°" /><Th t="Méthode" /><th /></tr></thead>
                <tbody>
                  {zonesTerrain.map((z, i) => (
                    <tr key={i} onMouseEnter={() => setSurvol(`terrain:${z?.nom ?? `terrain${i + 1}`}`)} onMouseLeave={() => setSurvol(null)}>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'terrain', 'zones', i, 'nom']} valeur={z?.nom} type="text" placeholder={`terrain${i + 1}`} bloc="ZoneTerrainGeo" cle="nom" libelle="Nom de la zone" /></td>
                      <td><CasesCotes ctx={ctx} chemin={['geometrie', 'terrain', 'zones', i, 'cotes']} valeur={z?.cotes} options={nomsCotes} /></td>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'terrain', 'zones', i, 'de']} valeur={z?.de} placeholder="début" bloc="ZoneTerrainGeo" cle="de" libelle="Début du tronçon" /></td>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'terrain', 'zones', i, 'a']} valeur={z?.a} placeholder="fin" bloc="ZoneTerrainGeo" cle="a" libelle="Fin du tronçon" /></td>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'terrain', 'zones', i, 'cote']} valeur={z?.cote} placeholder="—" bloc="ZoneTerrainGeo" cle="cote" libelle="Cote du terrain de la zone" /></td>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'terrain', 'zones', i, 'pente_beta']} valeur={z?.pente_beta} placeholder="—" bloc="ZoneTerrainGeo" cle="pente_beta" libelle="Pente β" /></td>
                      <td><Choix ctx={ctx} chemin={['geometrie', 'terrain', 'zones', i, 'methode_pente']} valeur={z?.methode_pente ?? 'surcharge_equivalente'} options={['surcharge_equivalente', 'coulomb_beta']} libelles={{ surcharge_equivalente: 'surcharge équivalente', coulomb_beta: 'Coulomb avec β' }} bloc="ZoneTerrainGeo" cle="methode_pente" libelle="Méthode" /></td>
                      <td><button className="btn icone discret" title="Supprimer" onClick={() => suppr(['geometrie', 'terrain', 'zones', i], `la zone de terrain ${z?.nom ?? i + 1}`)}><IconeCorbeille taille={14} /></button></td>
                    </tr>))}
                  {zonesTerrain.length === 0 && <tr><td colSpan={8} className="doux">Terrain horizontal à la cote donnée sur tous les côtés.</td></tr>}
                </tbody>
              </table>
            </>
          )} />
          {nouvelleForme && <button className="btn" style={{ marginBottom: 16 }} onClick={() => ctx.actions.ajouter(['geometrie', 'terrain', 'zones'], { nom: `terrain${zonesTerrain.length + 1}`, cotes: nomsCotes.slice(0, 1), pente_beta: 10 })}><IconePlus /> Ajouter une zone de terrain</button>}

          <Bloc titre="Fouille : zones de fond" enfants={(
            <>
              <div className="grille-form" style={{ padding: '6px 10px' }}>
                <label>Cote initiale côté fouille ({unite}){nouvelleForme ? <Champ ctx={ctx} chemin={['geometrie', 'fouille', 'cote_initiale']} valeur={geo.fouille?.cote_initiale} placeholder="= terrain côté terre" bloc="FouilleGeo" cle="cote_initiale" large libelle="Cote initiale côté fouille" /> : <span className="doux"> {m.terrain?.aval ?? '= terrain'}</span>}</label>
              </div>
              <table className="tableau compact">
                <thead><tr><Th t="Zone" titre="clé du bloc excaver des phases" /><Th t="Côtés" /><Th t="De" u="m" /><Th t="À" u="m" /><Th t="Largeur en plan" u="m" titre="vide : moitié de la distance au vis-à-vis" /><Th t="Fond par phase" /><th /></tr></thead>
                <tbody>
                  {zonesFond.map((z, i) => (
                    <tr key={i} onMouseEnter={() => setSurvol(`zone:${z?.nom}`)} onMouseLeave={() => setSurvol(null)}>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'fouille', 'zones', i, 'nom']} valeur={z?.nom} type="text" bloc="ZoneFondGeo" cle="nom" libelle="Nom de la zone de fond" /></td>
                      <td><CasesCotes ctx={ctx} chemin={['geometrie', 'fouille', 'zones', i, 'cotes']} valeur={z?.cotes} options={nomsCotes} /></td>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'fouille', 'zones', i, 'de']} valeur={z?.de} placeholder="début" bloc="ZoneFondGeo" cle="de" libelle="Début du tronçon" /></td>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'fouille', 'zones', i, 'a']} valeur={z?.a} placeholder="fin" bloc="ZoneFondGeo" cle="a" libelle="Fin du tronçon" /></td>
                      <td><Champ ctx={ctx} chemin={['geometrie', 'fouille', 'zones', i, 'largeur']} valeur={z?.largeur} placeholder="auto" bloc="ZoneFondGeo" cle="largeur" libelle="Largeur en plan" /></td>
                      <td className="doux" style={{ fontSize: 11.5 }}>
                        {phases.map((p, k) => {
                          const ex = p?.excaver
                          const v = ex && typeof ex === 'object' ? ex[String(z?.nom)] ?? ex.defaut : ex
                          return v === undefined || v === null ? null : <span key={k} className="mono" style={{ marginRight: 6 }}>{k + 1}: {String(v)}</span>
                        })}
                        <span className="faible"> (étape Phases, excaver : {'{ defaut: …, '}{String(z?.nom)}: … {'}'})</span>
                      </td>
                      <td><button className="btn icone discret" title="Supprimer" onClick={() => suppr(['geometrie', 'fouille', 'zones', i], `la zone de fond ${z?.nom}`)}><IconeCorbeille taille={14} /></button></td>
                    </tr>))}
                  {zonesFond.length === 0 && <tr><td colSpan={7} className="doux">Un seul fond de fouille pour toute l'enceinte (cote excaver de chaque phase).</td></tr>}
                </tbody>
              </table>
            </>
          )} />
          {nouvelleForme && <button className="btn" style={{ marginBottom: 16 }} onClick={() => ctx.actions.ajouter(['geometrie', 'fouille', 'zones'], { nom: `zone${zonesFond.length + 1}`, cotes: nomsCotes.slice(1, 2) })}><IconePlus /> Ajouter une zone de fond</button>}

          <Bloc titre="Fouille : risbermes, talus, gradins" enfants={(
            <table className="tableau compact">
              <thead><tr>{COLS_OBJET.map(([k, t, u]) => <Th key={k} t={t} u={u === 'COTE' ? unite : u} titre={doc(ctx.schema, 'ObjetTerrainGeo', k)} />)}<Th t="Côtés" /><th /></tr></thead>
              <tbody>
                {objets.map((o, i) => (
                  <tr key={i} onMouseEnter={() => setSurvol(`objet:${g.objets[i]?.nom}`)} onMouseLeave={() => setSurvol(null)}>
                    {COLS_OBJET.map(([k]) => (
                      <td key={k}>
                        {k === 'type' ? <Choix ctx={ctx} chemin={['geometrie', 'fouille', 'objets', i, 'type']} valeur={o?.type ?? 'risberme'} options={['risberme', 'talus', 'gradins']} bloc="ObjetTerrainGeo" cle="type" libelle="Type" />
                          : k === 'methode' ? <Choix ctx={ctx} chemin={['geometrie', 'fouille', 'objets', i, 'methode']} valeur={o?.methode ?? 'surcharge_equivalente'} options={Object.keys(LIBELLES_METHODE_OBJET)} libelles={LIBELLES_METHODE_OBJET} bloc="ObjetTerrainGeo" cle="methode" libelle="Méthode" />
                            : k === 'phases' ? <ChampPaire ctx={ctx} chemin={['geometrie', 'fouille', 'objets', i, 'phases']} valeur={o?.phases} bloc="ObjetTerrainGeo" cle="phases" libelle="Phases d'existence" placeholder="1re ; dernière" />
                              : <Champ ctx={ctx} chemin={['geometrie', 'fouille', 'objets', i, k]} valeur={o?.[k]} type={k === 'nom' ? 'text' : 'number'} bloc="ObjetTerrainGeo" cle={k} libelle={t(k)} placeholder={k === 'de' ? 'début' : k === 'a' ? 'fin' : k === 'nom' ? `${(o?.type ?? 'risberme')[0].toUpperCase()}${(o?.type ?? 'risberme').slice(1)}${i + 1}` : ''} />}
                      </td>))}
                    <td><CasesCotes ctx={ctx} chemin={['geometrie', 'fouille', 'objets', i, 'cotes']} valeur={o?.cotes} options={nomsCotes} /></td>
                    <td><button className="btn icone discret" title="Supprimer" onClick={() => suppr(['geometrie', 'fouille', 'objets', i], `l'objet ${g.objets[i]?.nom}`)}><IconeCorbeille taille={14} /></button></td>
                  </tr>))}
                {objets.length === 0 && <tr><td colSpan={COLS_OBJET.length + 2} className="doux">{nouvelleForme ? 'Aucun objet de terrain côté fouille.' : g.objets.length ? `${g.objets.length} objet(s) décrits dans le bloc fouille (forme ancienne).` : 'Aucun objet de terrain.'}</td></tr>}
              </tbody>
            </table>
          )} />
          {nouvelleForme && <button className="btn" style={{ marginBottom: 16 }} onClick={() => ctx.actions.ajouter(['geometrie', 'fouille', 'objets'], { nom: `R${objets.length + 1}`, type: 'risberme', cotes: nomsCotes.slice(0, 1), phases: [Math.max(1, phases.length), Math.max(1, phases.length)], cote_crete: -3, largeur_crete: 2, pente: 1.5, cote_pied: -6 })}><IconePlus /> Ajouter une risberme</button>}

          <Bloc titre="Surcharges positionnées en plan" enfants={(
            <table className="tableau compact">
              <thead><tr><Th t="Surcharge" /><Th t="Côtés" /><Th t="De" u="m" /><Th t="À" u="m" /><Th t="Centre x ; y" u="m" /><Th t="Emprise lx ; ly" u="m" /><th /></tr></thead>
              <tbody>
                {positions.map((p, i) => (
                  <tr key={i} onMouseEnter={() => setSurvol(`surcharge:${p?.surcharge}`)} onMouseLeave={() => setSurvol(null)}>
                    <td><Choix ctx={ctx} chemin={['geometrie', 'surcharges', i, 'surcharge']} valeur={p?.surcharge} options={surcharges} bloc="PositionSurchargeGeo" cle="surcharge" libelle="Surcharge" /></td>
                    <td><CasesCotes ctx={ctx} chemin={['geometrie', 'surcharges', i, 'cotes']} valeur={p?.cotes} options={nomsCotes} /></td>
                    <td><Champ ctx={ctx} chemin={['geometrie', 'surcharges', i, 'de']} valeur={p?.de} placeholder="début" bloc="PositionSurchargeGeo" cle="de" libelle="Début du tronçon" /></td>
                    <td><Champ ctx={ctx} chemin={['geometrie', 'surcharges', i, 'a']} valeur={p?.a} placeholder="fin" bloc="PositionSurchargeGeo" cle="a" libelle="Fin du tronçon" /></td>
                    <td><ChampPaire ctx={ctx} chemin={['geometrie', 'surcharges', i, 'position']} valeur={p?.position} bloc="PositionSurchargeGeo" cle="position" libelle="Centre en plan" /></td>
                    <td><ChampPaire ctx={ctx} chemin={['geometrie', 'surcharges', i, 'emprise']} valeur={p?.emprise} bloc="PositionSurchargeGeo" cle="emprise" libelle="Emprise" placeholder="lx ; ly" /></td>
                    <td><button className="btn icone discret" title="Supprimer" onClick={() => suppr(['geometrie', 'surcharges', i], `la position de ${p?.surcharge}`)}><IconeCorbeille taille={14} /></button></td>
                  </tr>))}
                {positions.length === 0 && <tr><td colSpan={7} className="doux">{nouvelleForme ? 'Aucune surcharge positionnée : les surcharges s\'appliquent à tous les côtés.' : g.positions.length ? `${g.positions.length} surcharge(s) positionnée(s) par leurs propres clés (forme ancienne).` : 'Aucune surcharge positionnée.'}</td></tr>}
              </tbody>
            </table>
          )} />
          {nouvelleForme && surcharges.length > 0 && <button className="btn" style={{ marginBottom: 16 }} onClick={() => ctx.actions.ajouter(['geometrie', 'surcharges'], { surcharge: surcharges[0], cotes: nomsCotes.slice(0, 1) })}><IconePlus /> Positionner une surcharge</button>}
        </div>
      </div>
      <ErreursBloc ctx={ctx} prefixe="geometrie" />
    </div>
  )
}

function t(k: string): string {
  return COLS_OBJET.find(([c]) => c === k)?.[1] ?? k
}
