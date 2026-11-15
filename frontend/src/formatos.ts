export const dataEHora = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

/** Formata data ISO simples ("2026-12-10") em "10/12/2026" sem deslocamento de fuso. */
export function dataCurta(valor: string | null): string {
  if (!valor) return '—'
  const partes = valor.split('-')
  return partes.length === 3 ? `${partes[2]}/${partes[1]}/${partes[0]}` : valor
}

/**
 * Valor em dinheiro, que a API manda como texto com duas casas ("1234.50"), em reais ("R$ 1.234,50").
 * Só mexe no texto: o valor nunca passa por ponto flutuante.
 */
export function reais(valor: string | null): string {
  if (valor === null) return '—'
  const [inteiro, centavos = '00'] = valor.split('.')
  const comMilhar = inteiro.replace(/\B(?=(\d{3})+(?!\d))/g, '.')
  return `R$ ${comMilhar},${centavos.padEnd(2, '0')}`
}

/** Soma exata em centavos inteiros de strings decimais ("10.50" ou "10,50"), sem ponto flutuante. */
export function somarCentavos(valores: string[]): string {
  let total = 0
  for (const bruto of valores) {
    const limpo = bruto.trim().replace(',', '.')
    if (!/^\d+(\.\d{1,2})?$/.test(limpo)) continue
    const [reaisParte, centParte = ''] = limpo.split('.')
    total += Number(reaisParte) * 100 + Number(centParte.padEnd(2, '0'))
  }
  const reaisParte = Math.floor(total / 100)
  const centParte = String(total % 100).padStart(2, '0')
  return `${reaisParte}.${centParte}`
}
