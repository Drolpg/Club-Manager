const REGEX_VIEWBOX = /viewBox="([0-9]+\s+[0-9]+\s+[0-9]+\s+[0-9]+)"/
const REGEX_PATH = /<path[^>]*d="([MmHhVvLlZz0-9\s.-]+)"/

/** Renderiza o QR Code Pix a partir dos atributos geométricos validados, sem injetar HTML. */
export function QrCodePix({ svg }: { svg: string }) {
  const matchVb = REGEX_VIEWBOX.exec(svg)
  const matchPath = REGEX_PATH.exec(svg)
  const viewBox = matchVb ? matchVb[1] : '0 0 29 29'
  const caminho = matchPath ? matchPath[1] : ''

  return (
    <svg
      role="img"
      aria-label="QR Code Pix"
      viewBox={viewBox}
      shapeRendering="crispEdges"
      width={180}
      height={180}
    >
      <rect width="100%" height="100%" fill="#ffffff" />
      {caminho && <path fill="#000000" d={caminho} />}
    </svg>
  )
}
