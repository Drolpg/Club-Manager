export const dataEHora = new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' })

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
