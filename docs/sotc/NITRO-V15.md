# Nitro V15: primeira rodada de diagnóstico e buffers

Meta: **1920×1080 nativo, 60 fps estáveis**. Esta versão é experimental; a meta
ainda não foi demonstrada. Não há validação de campanha, combate ou longa duração.

## Base e alterações

- Fork: <https://github.com/DanielTR048/ShadowOfTheColossus-PC>, branch
  `codex/nitro-v15-buffers`.
- Base upstream: `a0cab70355b7e26183a9faff512b52cc71171942` (v0.56).
- Ensaio adaptado de `FelipePrado0/gow3_pc`, commit
  `af5930a0e3bb6bd257563d0bfd6fa09210a78310`, sob GPL-2.0-or-later.
  `SOTC_STREAM_MEMORY=device|host|cached` escolhe onde alocar os buffers Stream.
  `device` mantém a preferência original por memória da GPU; `host` prefere RAM;
  `cached` também solicita cache de CPU e acesso aleatório, como no GoW3.
  A preferência não garante o tipo escolhido: `SOTC_BUFFER_DIAG=1` mostra as
  propriedades reais. Texturas e buffers DeviceLocal mantêm a política original.
- `SOTC_FRAME_CSV` registra intervalos entre chamadas de apresentação. Não mede
  tempo de GPU nem a exibição física na tela.
- Correção do estouro da fila de notificações de memória: o piloto parou com
  `STOP: GPU hook queue overflow`. A fila passa de 64 para 4096 entradas, ainda
  limitada; unmap já notificado deixa de enfileirar duplicatas descartáveis.
  Callbacks continuam fora do lock. Isto não prova que qualquer carga caiba na fila.
- Correção de LOD: com `linger=0`, o código original informava que até as texturas
  usadas no relatório atual estavam sem uso. O relatório agora preserva esses
  bancos. Mantido o mip 2 padrão do upstream; não é uma promessa de texturas no
  máximo. Resolução nativa e qualidade dos mips são coisas distintas.
- `sotc.py --prepare-only` prepara as imagens em `out/`, sem iniciar o jogo.

## Ambiente e método

Notebook Acer Nitro ANV15-52, i7-13620H, 32 GB de RAM, RTX 4050 Laptop de 6 GB,
driver NVIDIA 610.88. Ligado à tomada, plano de energia existente mantido.
Compilação MSYS2 CLANG64, `RelWithDebInfo`, `-O2`, sem LTO/PGO.

Jogo CUSA08809 com atualização local; patch `fps60`; `SOTC_NEO=0`;
`BB_VBLANK_HZ=120`; saída 1920×1080; FSR1 e RCAS desligados. O log confirma
entrada e saída 1920×1080. CVars padrão do launcher Python:
`doIndexBufferCulling=0 doSunShadowIndexBufferCulling=0`. Nenhum ajuste de distância
de renderização foi aplicado. O programa escolheu a RTX 4050; o orçamento Vulkan
livre era menor que os 6 GB totais, como é normal com outros programas abertos.

Cada execução usa uma pasta nova em `.local/bench/`, uma cópia dos saves e um
cache de aplicação inicialmente vazio. O cache do driver NVIDIA não foi apagado.
O par A/B usa o mesmo executável e as mesmas imagens preparadas, sem entrada de
controle: abertura automática, janela de 40–110 segundos desde a primeira
apresentação. A captura aos 118 segundos desde o início do processo fica fora da
medição. Compilação de shaders e streaming **fazem parte** desse ensaio frio.
O avanço da abertura pode variar com o desempenho; não é um benchmark determinista
de gameplay nem uma medição de câmera fixa após aquecimento.

FPS médio = apresentações no intervalo / duração completa do intervalo. O resumo
só confirma essa média quando o CSV demonstra que a execução passou do fim da
janela. Percentis e 1% low usam intervalos completos dentro da janela; travadas
que cruzam suas bordas afetam a média, mas não esses percentis. A média dos
intervalos também é registrada separadamente. Não se calcula média de FPS
instantâneo, que esconderia travadas.

`nvidia.csv` mede a GPU inteira (inclusive outros aplicativos), uma vez por
segundo. `process.csv` registra CPU do processo, com 100% equivalente a um núcleo,
e memória residente. Esses indicadores sugerem gargalos, mas não substituem um
perfil de CPU/GPU por função.

## Resultado de 14/10/2026

| Execução | FPS médio | 1% low | p95 do intervalo | Maior intervalo completo |
|---|---:|---:|---:|---:|
| A1 — device | 19,00 | 1,69 | 66,50 ms | 5.767 ms |
| B1 — cached | 22,16 | 4,34 | 58,80 ms | 1.259 ms |
| B2 — cached | falhou antes do primeiro quadro | — | — | — |
| A2 — device | falhou antes do primeiro quadro | — | — | — |

**Não há ganho repetível demonstrado.** O primeiro par favoreceu `cached`, mas a
repetição na ordem inversa terminou com `0xC0000005` em ambos. Um teste adicional
com `device` e cache de pipelines desligado também falhou antes do primeiro quadro.
Os dois runs completos foram encerrados pelo limite programado de 125 segundos;
seu `exit_code=1` vem desse encerramento, não de uma queda espontânea.

O tipo real de memória mudou como esperado: Stream de 128 MiB passou do tipo 4
(`device_local=1`, `host_cached=0`) para o tipo 3 (`device_local=0`,
`host_cached=1`), ambos coerentes e visíveis à CPU. O buffer GDS de 0,1 MiB também
é classificado como Stream e segue a opção, assim como na adaptação do GoW3.

Nos intervalos aproximados da telemetria, a utilização média da GPU inteira foi
44,8%/39,7%, com picos de memória de 4.328/4.020 MiB e temperatura máxima de
63/64 °C, respectivamente. A CPU do processo usou em média o equivalente a
3,82/3,92 núcleos. Não houve evidência de GPU continuamente a 100%; isso não
identifica sozinho qual espera ou etapa limita o desempenho.

As duas capturas finais mostram a mesma sequência da floresta em instantes
diferentes. Não há imagem congelada, câmera fixa nem alinhamento por frame do jogo.
Portanto, esta é uma sondagem inicial com carga semelhante, não uma medida causal
precisa de ganho. Os 2 fps relatados na instalação antiga também não são baseline
comparável: executável, configuração e cena diferem. Não se deve afirmar ganho de
2 para 22 fps a partir destes dados.

Dados resumidos e hash do executável estão em
[`nitro-v15-results.json`](nitro-v15-results.json). Logs, CSVs brutos e capturas
ficam nas pastas `.local/bench/<run_id>/` indicadas ali. O resumo recalculado usa
o CSV original e está em `recomputed-summary.json`; os primeiros `summary.json`
foram gerados antes de separar FPS da janela e média dos intervalos.

## Execução isolada neste computador

Execute `Play-Nitro.cmd` na raiz. O preset usa 1080p nativo, patch de 60 fps e
buffers `device`, preservando a preferência upstream até haver evidência de ganho
repetível. O limite desbloqueado não garante 60 fps.

O arquivo privado `.local/nitro.json` aponta para o dump, a atualização e os
módulos já existentes. O jogo usa **`.local/play-user/savedata`**, inicializado
com uma cópia do backup. Saves seguintes ficam nessa cópia. O log fica em
`.local/play-user/last_run.log`. Há falha intermitente de inicialização antes do
primeiro quadro (`0xC0000005`) nos dois modos de buffer, com cache novo ou copiado.
Desligar o cache em disco (`BB_PIPELINE_CACHE=0`) também não resolveu no ensaio.
O preset preserva a política upstream; ele não é uma versão estável para jogar.

Não execute o launcher original para testar este fork. O preset não modifica a
instalação original, seus saves ou `%APPDATA%/sotc-launcher/settings.json`.
`.local/backup/` contém backup dos saves/configuração e inventário SHA-256 da
instalação. Imagens preparadas em `out/` e dados privados de `.local/` não são
versionados nem enviados ao GitHub.

Exemplo de configuração para outro computador, usando caminhos próprios:

```json
{
  "game": "D:/meu-dump/CUSA08809",
  "update": "D:/meu-dump/CUSA08809-patch",
  "sys_modules": "D:/meus-modulos",
  "save_template": "D:/backup/savedata",
  "stream_memory": "device"
}
```

## Reproduzir o ensaio

Primeiro compile conforme o projeto original e crie `out/venv` com `iced-x86`,
`pillow` e `psutil`. No PowerShell, com os caminhos próprios:

```powershell
$env:SOTC_GAME_DIR = 'D:/meu-dump/CUSA08809'
$env:SOTC_UPDATE_DIR = 'D:/meu-dump/CUSA08809-patch'
$env:SOTC_SYS_MODULES = 'D:/meus-modulos'
$env:SOTC_MODES = 'fps60'
$env:SOTC_USER_DIR = "$PWD/.local/prepare-user"
.\out\venv\Scripts\python.exe sotc.py --prepare-only
.\out\venv\Scripts\python.exe tools/sotc_benchmark.py `
  --game $env:SOTC_GAME_DIR --update $env:SOTC_UPDATE_DIR `
  --save-template 'D:/backup/savedata' --stream-memory device `
  --seconds 125 --warmup 40 --measure-end 110 --capture 118 --label ab-device
```

Repita com `--stream-memory cached`, sem `--cache-template`. Eventos e capturas
contam tempo desde a criação do processo; a janela de medição conta desde a
primeira apresentação. Mantenha os demais arquivos e parâmetros iguais e não
compile, faça cópias grandes ou rode outro jogo durante a medição. Não compare
cenas diferentes como se fossem o mesmo teste.

Para avaliar um cache já aquecido, `--cache-template` copia apenas `shader/` e
`cache/` de uma execução anterior. Não misture execuções com cache frio e quente
no mesmo comparativo. `--env NOME=valor` permite diagnósticos,
mas os caminhos isolados e as configurações centrais do ensaio têm precedência.

## Validação e próximos gargalos

Passaram 5 testes Python do resumo de benchmark, 6 testes existentes de preparação
e os executáveis `gpu-hook-queue-test` e `sotc-lod-stats-test`. Cobrem a média com
travadas, as bordas da janela, a fila de mais de 64 callbacks com reentrada e os
bancos LOD com linger zero. A compilação completa passou; isso e os testes não
comprovam estabilidade durante toda a campanha. Os patches em
`gpu/third_party/fsr-vulkan` são os já aplicados pelo `build.sh` upstream, sem
alteração do gitlink nesta branch.

A conferência após os testes verificou os 7.377 hashes da instalação original sem
alteração (incluindo seus saves), os metadados de 516 arquivos do dump/atualização
sem alteração e o mesmo hash das configurações globais do launcher. Resultado
privado em `.local/backup/verification.json`.

Pilotos alcançaram a abertura e a tela de título, mas registraram pausas longas,
erros `ComputeOffset ... Phi` e esperas `PS4SyncEvent`. Após pular a abertura,
houve trechos com mais de 20 mil comandos indiretos por quadro e FPS de um dígito.
Os pilotos tiveram entrada manual e capturas: não são usados como resultado A/B.
Não houve validação de combate nem de percurso jogável nesta rodada. A repetição
do A/B na ordem inversa falhou antes do primeiro quadro nos dois modos; isso impede
atribuir o ganho observado em um único par ao posicionamento dos buffers.

A próxima investigação deve separar compilação/streaming de custo constante,
obter uma cena jogável repetível e perfilar a preparação dos milhares de draws,
barreiras e esperas CPU/GPU. Reduzir distância de renderização só será útil se
reduzir o trabalho que efetivamente domina o quadro. Não há fundamento ainda para
prometer 60 fps com esse ajuste ou para atribuir o problema apenas à potência da GPU.
