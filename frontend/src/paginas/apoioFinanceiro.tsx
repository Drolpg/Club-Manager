import { useId } from 'react'
import { type Motivo } from '../api/aprovacoes'
import { Selecao } from '../componentes'

export function AreaDeTexto({
  rotulo,
  valor,
  aoMudar,
  erros,
  linhas = 3,
}: {
  rotulo: string
  valor: string
  aoMudar: (valor: string) => void
  erros?: string[]
  linhas?: number
}) {
  const id = useId()
  return (
    <div className="campo">
      <label htmlFor={id}>{rotulo}</label>
      <textarea
        id={id}
        rows={linhas}
        maxLength={1000}
        value={valor}
        onChange={(evento) => aoMudar(evento.target.value)}
        aria-invalid={!!erros?.length}
      />
      {erros?.map((erro) => (
        <p key={erro} className="erro-de-campo">
          {erro}
        </p>
      ))}
    </div>
  )
}

export function SeletorDeMotivo({
  motivos,
  valor,
  aoMudar,
  erros,
}: {
  motivos: Motivo[]
  valor: string
  aoMudar: (valor: string) => void
  erros?: string[]
}) {
  return (
    <>
      <Selecao rotulo="Motivo" value={valor} aoMudar={aoMudar}>
        <option value="">Escolha um motivo</option>
        {motivos.map((m) => (
          <option key={m.id} value={m.id}>
            {m.texto}
          </option>
        ))}
      </Selecao>
      {erros?.map((erro) => (
        <p key={erro} className="erro-de-campo">
          {erro}
        </p>
      ))}
    </>
  )
}
