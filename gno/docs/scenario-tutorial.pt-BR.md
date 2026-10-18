# Tutorial: montando a apresentação de um cenário

*Read in English: [scenario-tutorial.md](scenario-tutorial.md).*

Este tutorial monta, passo a passo, a apresentação gráfica do cenário
`Recepção` de um caso clínico sobre sífilis no pré-natal. Ao final, o Player
mostra cada cena desse cenário sobre a imagem da recepção, com uma caixa de
fala embaixo e as escolhas abaixo dela:

![O cenário pronto no Player, com a caixa de fala e duas escolhas](images/scenario-tutorial/09-player-choices.jpg)

Tudo acontece em **Presentation → Scenarios**. A referência completa do que os
IDs e os contêineres fazem durante a execução está em
[Graphic play](../README.md#graphic-play), no README.

## Antes de começar

A narrativa já deve ter cenas no cenário `Recepção` (um título como
`# Abertura: Recepção (Start)`), e a apresentação precisa de imagens:

1. **Presentation → Image Libraries:** adicione a biblioteca com as imagens do
   caso (aqui, `https://mundorum.github.io/harena-cases/ethics/syphilis/images/`).
2. **Presentation → Entity:** associe as entidades da narrativa às suas
   imagens. As duas peças de interface usadas abaixo não aparecem na
   narrativa; declare-as em *Add entity* e dê a cada uma a sua imagem:
   `@Caixa_de_Diálogo` (uma caixa de diálogo) e `@Caixa_de_Opção` (uma caixa
   de opção).

Depois abra **Presentation → Scenarios** e clique em `Recepção` para abrir o
seu design. O botão **Wide editor** (no canto superior direito) esconde o
restante do aplicativo e deixa a janela inteira para a área de desenho; todas
as imagens abaixo foram capturadas nesse modo.

## 1. Inserir a imagem de fundo

Clique em **Choose background** e escolha a imagem `Recepção` no seletor.

![O seletor de fundo, com as imagens da biblioteca](images/scenario-tutorial/01-choose-background.png)

A área de desenho assume o tamanho original da imagem (aqui, 1672 × 941 px).
Ajuste em **Canvas size** o tamanho em que o cenário será apresentado: ative
o cadeado ao lado para manter a proporção e digite `1007` na largura; a
altura acompanha (`567`). Também é possível arrastar o canto inferior direito
da área, segurando Shift para manter a proporção. O fundo sempre preenche a
área inteira.

![A área de desenho com o fundo da recepção, em 1007 × 567](images/scenario-tutorial/01-background.jpg)

## 2. Inserir uma entidade e um texto

**Uma entidade.** Arraste o quadro `@Caixa_de_Diálogo` de *Available
entities* (na barra lateral, abaixo da hierarquia) para a área de desenho.
Ela chega como uma imagem de 80 × 80 cujo ID é o nome da entidade,
`caixa_de_dialogo`.

Ative **Edit**: nesse modo, um clique seleciona um item e a barra lateral
mostra as suas propriedades. Mova e redimensione a caixa arrastando-a e
arrastando a alça do canto inferior direito, ou digite os valores no
inspetor. No exemplo, a caixa tem `900 × 80` e fica em `45, 386`.

![A entidade da caixa de diálogo selecionada, com o seu inspetor](images/scenario-tutorial/02-entity.jpg)

**Um texto.** Ative **Place: Text** e arraste um retângulo sobre a caixa. A
nova área de texto recebe o ID `text_1`, e o editor volta para Edit com ela
selecionada. No inspetor, defina a fonte, o tamanho e a cor; *Initial text*
serve apenas para o design e é substituído durante a execução. No exemplo, a
área de texto tem `860 × 60`, fica em `67, 397` e usa Lora 18 px, em preto.

![A área de texto desenhada sobre a caixa de diálogo](images/scenario-tutorial/02-text.jpg)

Por enquanto, os dois são itens comuns: o Player ainda não faria nada com
eles. O que lhes dá um papel é o ID.

## 3. As categorias de IDs

Durante a execução, o gnō procura itens com certos IDs e os preenche. Quando
um item está selecionado, o inspetor sugere esses IDs como botões em
*Suggested IDs*; um clique em um deles renomeia o item.

![O inspetor sugerindo os IDs de papel](images/scenario-tutorial/03-suggested-ids.png)

| ID | Papel da área de texto | De onde vem o texto |
|---|---|---|
| `speech` | A área de fala geral. | Tudo o que é dito no trecho: a narração (a menos que exista `_.speech`) e os diálogos (das entidades que não têm área própria). |
| `_.speech` | A área do narrador. | O texto livre da cena, escrito fora de qualquer diálogo. |
| `entity.speech` | A área própria de uma entidade, como `Luísa.speech` (com o ID da entidade no lugar de `entity`). | Os diálogos dessa entidade: `-- @Luísa: …`. |
| `action_N` | A escolha número N: `action_1`, `action_2`, … | O rótulo do N-ésimo desvio da cena (`* Rótulo -> Destino`). Um clique leva ao destino desse desvio. |

Algumas regras fazem esses IDs funcionarem juntos:

- **Pares.** Uma área de texto e uma entidade podem ter o *mesmo* ID. Assim,
  elas cumprem o papel juntas: a área de texto mostra o texto e a entidade é
  a sua imagem (o balão de fala, o botão). No SVG exportado, o ID da área de
  texto ganha o sufixo `_text` (`speech` e `speech_text`); no editor aparece
  apenas o ID digitado.
- **Mostrar e esconder.** Uma área de fala sem nada para mostrar na pausa
  atual fica escondida, assim como uma escolha que não está sendo oferecida.
  A entidade do par se esconde junto.
- **Quem está falando.** Quando diálogos de entidades diferentes dividem a
  área `speech`, cada um é precedido pelo nome de quem fala.
- **Alternativas.** Se o design não tem área para um texto, ele não é
  mostrado. Se falta um `action_N` para uma escolha, o Player mostra o seu
  botão comum para ela abaixo do cenário, para que a cena nunca fique travada.

As sugestões também incluem `action_proceed` (continuar depois de uma pausa)
e `action_regress` (voltar um trecho), os controles para avançar pela cena.

Neste tutorial, a `Recepção` recebe uma única área `speech`, usada tanto pela
narração quanto pelos diálogos, e duas escolhas, `action_1` e `action_2`.

## 4. O par `speech`, agrupado

Selecione a entidade da caixa de diálogo e clique no botão `speech` (ou
digite `speech` em *ID*). Faça o mesmo com a área de texto. Agora os dois
formam um par.

Em seguida, coloque-os em um *grupo*, para que se movam juntos e a caixa só
apareça enquanto houver fala. No painel **Hierarchy**, clique em uma das duas
linhas `speech` e clique na outra segurando Shift ou Ctrl, para que as duas
fiquem selecionadas:

![Os dois itens do par speech selecionados na hierarquia](images/scenario-tutorial/04-speech-select.jpg)

Clique no primeiro botão no topo da hierarquia, **Group the selected items**.
O novo grupo se chama `group_1`; renomeie-o para `group_speech`.

![O grupo group_speech, com a entidade e a área de texto](images/scenario-tutorial/04-speech-group.jpg)

Um grupo não tem área própria: ele é apenas os seus itens, desenhados de trás
para a frente na ordem mostrada em *Items, back to front* (primeiro a imagem,
para que o texto fique por cima).

Outra forma de montar um grupo: clique em **New group** na barra de
ferramentas, depois clique nos itens que devem entrar nele, na área de
desenho ou na hierarquia, e clique em **Done inserting**.

## 5. O par `action_1`, agrupado

A primeira escolha é montada da mesma forma, com a caixa de opção:

1. Arraste `@Caixa_de_Opção` para a área de desenho e ajuste o tamanho:
   `440 × 80` em `45, 474`.
2. Com **Place: Text**, desenhe uma área de texto sobre ela: `400 × 60` em
   `66, 485`.
3. Dê aos dois o ID `action_1`.
4. Selecione os dois na hierarquia, agrupe-os e renomeie o grupo para
   `group_action_1`.

![O grupo group_action_1 selecionado](images/scenario-tutorial/05-action-1-group.jpg)

## 6. O par `action_2`, agrupado

Repita para a segunda escolha, à direita da primeira:

1. Caixa de opção: `440 × 80` em `493, 474`.
2. Área de texto: `400 × 65` em `513, 482`.
3. ID `action_2` para os dois.
4. Agrupe-os como `group_action_2`.

![O grupo group_action_2 selecionado, ao lado de group_action_1](images/scenario-tutorial/06-action-2-group.jpg)

A hierarquia agora tem três grupos, cada um com o seu par.

## 7. Uma pilha horizontal: `layout_actions`

Uma *pilha* (stack) posiciona os seus itens como um flexbox do CSS: uma pilha
horizontal os alinha da esquerda para a direita, cada um com o seu próprio
tamanho. Ela também ignora os itens escondidos, de modo que uma cena com uma
única escolha não deixa um buraco onde estaria a segunda.

1. Ative **Place: Horizontal stack** e arraste um retângulo em volta dos dois
   grupos de ação. A pilha se chama `layout_1`; renomeie-a para
   `layout_actions`.
2. No inspetor, clique em **Insert items** e clique em `group_action_1` e
   depois em `group_action_2` (clicar nas linhas da hierarquia é o jeito mais
   fácil). A ordem dos cliques é a ordem na pilha. Clique em **Done
   inserting**.
3. Defina *Along* como `Left`, *Across* como `Top` e *Gap* como `8`.

![A pilha horizontal layout_actions e as suas configurações](images/scenario-tutorial/07-layout-actions.jpg)

O atalho: selecione os dois grupos na hierarquia e clique no terceiro botão
no topo dela, **Put the selected items in a new horizontal stack**.

## 8. Uma pilha vertical, alinhada embaixo

O último contêiner empilha a fala acima das escolhas:

1. Ative **Place: Vertical stack** e arraste um retângulo sobre a parte de
   baixo do cenário, cobrindo a caixa de fala e as escolhas. Renomeie a pilha
   para `layout_speech_actions`. (No exemplo, ela tem `913 × 180` e fica em
   `45, 381`.)
2. **Insert items:** primeiro `group_speech` (em cima), depois
   `layout_actions` (embaixo). Pilhas podem conter outras pilhas.
3. Defina *Along* como **`Bottom`**, *Across* como `Left` e *Gap* como `8`.

![A pilha vertical layout_speech_actions, com Along em Bottom](images/scenario-tutorial/08-layout-speech-actions.jpg)

É o *Along = Bottom* que faz o design se adaptar à cena. A pilha encosta os
seus itens visíveis na borda de baixo:

- Enquanto a cena apenas narra (sem escolhas oferecidas), `layout_actions`
  fica escondida e não ocupa espaço, então a caixa de fala fica bem embaixo
  no cenário.
- Quando as escolhas aparecem, elas ocupam a parte de baixo e empurram a
  caixa de fala para cima delas.

## O resultado

Escolha **Player** e execute a narrativa. No primeiro trecho da cena de
abertura ainda não há escolhas, então a fala fica embaixo:

![O Player durante uma narração: a caixa de fala embaixo](images/scenario-tutorial/09-player-speech.jpg)

No final da cena, as escolhas são oferecidas: as duas caixas de opção ocupam
a parte de baixo e a caixa de fala sobe:

![O Player nas escolhas: a caixa de fala sobe acima delas](images/scenario-tutorial/09-player-choices.jpg)

A cena de abertura tem três desvios, mas o design tem apenas `action_1` e
`action_2`; a terceira escolha aparece como o botão comum do Player, abaixo
do cenário. Adicione um par `action_3` a `layout_actions` para trazê-la
também para dentro do cenário.

Para guardar o trabalho, use **Save** (armazenamento do navegador) ou
**Download**, que exporta um zip em que o design é `scene/recepcao.svg`.

## Indo além

O design real da `Recepção` também tem:

- **Âncoras** (`direita`, `esquerda`, `entrando`, `frente`): os lugares onde
  os personagens ficam. Arraste a imagem de um personagem para a área de
  desenho, ajuste o tamanho e clique em **Convert to anchor** no inspetor; a
  narrativa então posiciona as entidades pelo nome da âncora, como em
  `@Luísa direita feliz`.
- Uma entidade **`action_proceed`** (`@Botão_de_Próximo`), o botão de seta
  mostrado enquanto a cena está pausada, para continuar.

O comportamento de cada um durante a execução está descrito em
[Graphic play](../README.md#graphic-play).
