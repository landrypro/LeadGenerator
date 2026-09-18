import { access, cp, mkdir } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'


const clientRoot = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const repositoryRoot = resolve(clientRoot, '..')
const manualSource = join(
  repositoryRoot,
  'docs',
  'manuel-utilisateur',
  'Marketteo_CRM_Manuel_Utilisateur_v0.10.html',
)
const imagesSource = join(repositoryRoot, 'docs', 'manuel-utilisateur', 'images')
const publicationDirectory = join(clientRoot, 'public', 'manuel-utilisateur')


await access(manualSource)
await access(imagesSource)
await mkdir(publicationDirectory, { recursive: true })
await cp(manualSource, join(publicationDirectory, 'index.html'))
await cp(imagesSource, join(publicationDirectory, 'images'), { recursive: true })
