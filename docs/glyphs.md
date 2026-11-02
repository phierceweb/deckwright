# Glyphs — which name to reach for

A curated index into the vendored glyph set: names grouped by what the slide is about,
each with the moment to use it. Read it when you know what a mark should *mean* and not
what it is called.

It is a shortlist, not the vocabulary. 4,001 Material Symbols ship, so a name this page
never mentions very probably resolves — guess the upstream one, and a miss names the
closest real glyphs.

Names are written exactly as you type them into `icon:`. **Bold** entries are curated
aliases — a name deckwright maps onto a glyph the set calls something else. Everything else
is the glyph's own name, and the hyphenated spelling of an underscored one works too, so
`rocket-launch` and `rocket_launch` reach the same file. Which glyph each curated name
lands on is [`docs/icons.md`](icons.md#the-names-decks-are-already-written-against).

Placing an `icon:` is [`docs/components.md`](components.md#icon--a-vector-mark); how the
lookup resolves a name is [`docs/icons.md`](icons.md#the-search-order).

---

**Have the word already?** `deckwright glyphs find <substring>` searches all 4,001
names and the aliases, so you need this page only when you are looking for the word
itself.

## Table of Contents

- [Plain shapes and marks](#plain-shapes-and-marks)
- [Direction and momentum](#direction-and-momentum)
- [Money](#money)
- [Charts, when the chart itself is not on the slide](#charts-when-the-chart-itself-is-not-on-the-slide)
- [People](#people)
- [Product and engineering](#product-and-engineering)
- [AI](#ai)
- [Process and status](#process-and-status)
- [Risk, security, compliance](#risk-security-compliance)
- [Time](#time)
- [Talking to people](#talking-to-people)
- [Places and industry](#places-and-industry)
- [Documents](#documents)
- [Interface verbs](#interface-verbs)
- [Sustainability and hardware](#sustainability-and-hardware)

---

## Plain shapes and marks

Geometry rather than meaning — a bullet, a rule's end, a legend swatch.

**Five of these are not glyphs at all.** `circle`, `square`, `triangle`, `diamond` and
`ring` are drawn as DrawingML presets, because for these the geometry *is* the meaning
and an icon set only ever draws its idea of one: Material's square is round-cornered,
and a scan of all 4,001 found no rhombus anywhere. A preset is exact at any size and arrives as a shape a reader can grab a
handle on. A directory you configure still wins — ship your own `circle.svg` and you
get it. See [`icons.md`](icons.md#plain-shapes-are-presets-not-art).

| Name | Reach for it when… |
|---|---|
| **`plus`** / **`minus`** | adding or removing, or a plain ± |
| `circle` / `square` | a filled bullet the theme colours |
| **`ring`** | the same bullet, hollow |
| **`triangle`** | a solid up-pointing wedge |
| `diamond` | a rhombus — a node, a decision, a plain marker |
| `star` | a rating, a favourite, a highlight |
| **`heart`** | affection, a saved item, satisfaction |
| **`grid`** | a set of equal things, or a layout |
| `check` / `close` | a tick and a cross |

## Direction and momentum

| Name | Reach for it when… |
|---|---|
| **`arrow-up`** / **`arrow-down`** | a plain directional arrow, no trend implied |
| **`arrow-left`** / **`arrow-right`** | back and forward, or a step in a sequence |
| `rocket_launch` | something is shipping, launching, or going live |
| **`deploy`** | a release is going out — the same mark, when "deploy" is the word |
| **`momentum`** | the same mark again, for a slide about acceleration |
| **`growth`** | a number is going up and that is the point |
| **`decline`** | a number is going down — cost, churn, latency |
| **`steady`** | the line is flat and flat is the finding |
| `insights` | the slide is the moment the pattern became visible |
| **`forecast`** | the same mark, pointed forward rather than back |
| `route` | there is a path from here to there with turns in it |
| **`roadmap`** | same, when the audience calls it a roadmap |
| **`milestone`** | marking the point a phase is declared done |
| `explore` | the work is open-ended and the direction is the question |
| `travel_explore` | scanning a wide landscape before choosing |
| **`research`** | the same mark, for investigation rather than search |
| `timeline` | the argument is chronological |
| `history` | referring back to what the system already did |
| `update` | something is being refreshed rather than replaced |

## Money

| Name | Reach for it when… |
|---|---|
| `payments` | money moving, generically |
| **`revenue`** | the number on the slide is money coming in |
| **`cost`** | the number is money going out |
| **`budget`** | discussing an allocation rather than a flow |
| **`bank`** | an institution, a treasury, a reserve |
| **`invoice`** | billing, statements, itemised charges |
| `savings` | money set aside, or a saving the work created |
| `paid` | a thing is settled, no longer outstanding |
| `credit_card` | payment *method* is the subject |
| `currency_exchange` | conversion, FX, or a rate |
| **`pricing`** | the pricing model or a price change |
| `receipt_long` | a long itemised record — an audit trail of spend |

## Charts, when the chart itself is not on the slide

| Name | Reach for it when… |
|---|---|
| **`chart-bar`** | quantities compared across categories |
| **`chart-line`** | a value over time |
| **`chart-pie`** | shares of one total |
| **`chart-area`** | a filled trend over time |
| **`chart-scatter`** | correlation, spread, per-item points |
| **`chart-bubble`** | three dimensions, the third being size |
| **`chart-donut`** | composition where the middle can hold a number |
| **`chart-stacked`** | parts of a whole across categories |
| **`chart-waterfall`** | the bridge from one total to another |
| **`chart-candlestick`** | ranges and highs/lows over time |
| **`chart-gauge`** | one number against a target |
| **`metric`** | pointing at a measurement, not a chart |
| **`ranking`** | an ordered list where position is the message |
| `analytics` | the practice of measuring, not one measurement |
| `table_chart` | the data is tabular and that matters |
| **`spreadsheet`** | the source really is a spreadsheet |

## People

| Name | Reach for it when… |
|---|---|
| **`user`** | one person, generically |
| **`users`** | two or more, generically |
| **`team`** | a group acting as one unit |
| **`meeting`** | the same group, in a room |
| **`audience`** | the people being *reached*, not the people working |
| `diversity_3` | composition of a group is the subject |
| **`customer`** | the person on the other side of the product |
| `support_agent` | service, help desk, human-in-the-loop |
| **`hire`** | adding a person — headcount, onboarding |
| **`org-chart`** | reporting lines and structure |
| **`role`** | a named responsibility rather than a person |
| **`profile`** | an individual account or identity |
| `handshake` | agreement reached, partnership, a deal |
| `school` | training as an institution |
| **`learning`** | the same mark, for the act of learning |
| `workspace_premium` | a standard met, a certification |
| **`award`** | the same mark, when the word is "award" |
| `emoji_events` | a win worth celebrating |

## Product and engineering

| Name | Reach for it when… |
|---|---|
| **`bug`** | a defect, found or fixed |
| **`test`** | verification, experiments, the lab |
| `construction` | work in progress, deliberately unfinished |
| **`pipeline`** | staged automated processing |
| **`automation`** | a manual step that stopped being manual |
| `terminal` | the interface is a command line |
| **`console`** | the same mark, when the word is "console" |
| `code` | source, generically |
| `data_object` | a payload, a schema, a JSON shape |
| **`payload`** | same, when "payload" is the word on the slide |
| `api` | a contract between two systems |
| **`integration`** | wiring two systems together |
| **`model`** | a deployed artefact rather than a running service |
| **`server`** | infrastructure that answers requests |
| **`network`** | the wiring between machines rather than one of them |
| `storage` | data at rest |
| `database` | a database specifically |
| `memory` | RAM, caching, or the working set |
| `cloud_sync` | keeping two places in agreement |
| `extension` | a plug-in or optional capability |
| **`release`** | a version reaching users |
| **`version`** | which version is being discussed |
| `engineering` | the discipline, not a specific task |
| `architecture` | structural design decisions |

## AI

| Name | Reach for it when… |
|---|---|
| **`ai`** | the generic "this is the AI part" mark |
| **`agent`** | software acting on its own initiative |
| **`brain`** | reasoning, cognition, a mental model |
| `neurology` | the network itself, more literal than `brain` |
| **`token`** | cost or throughput measured in tokens |
| `dataset` | the training or evaluation corpus |
| `model_training` | the fitting step specifically |
| **`embedding`** | vectors, similarity, the latent space |
| **`prompt`** | the instruction given to a model |
| `manage_search` | retrieval with filters or structure |
| **`query`** | asking the system a question |
| `psychology_alt` | how a model behaves rather than how it works |

## Process and status

| Name | Reach for it when… |
|---|---|
| **`success`** | a step completed cleanly |
| **`failure`** | a step did not |
| **`blocker`** | progress is stopped by something external |
| **`pending`** | waiting, not stuck |
| `task_alt` | one item, done |
| **`done`** | when "done" is the word being used |
| **`todo`** | a list of things not yet started |
| `checklist` | a procedure with steps to tick |
| **`decision`** | the path forks here |
| **`phase`** | one segment of a longer sequence |
| **`backlog`** | queued work with no date on it |
| **`priority`** | this one first |
| `error` | something is wrong right now |
| `crisis_alert` | wrong *and* urgent |
| **`alert`** | a notification that needs a human |
| **`bell`** | a plain bell — an alert with no urgency attached |
| `notifications` | the notification mechanism itself |
| **`approve`** / **`reject`** | a gate with a person behind it |
| **`question`** | an open question on the slide |

## Risk, security, compliance

| Name | Reach for it when… |
|---|---|
| **`compliance`** | meeting an external standard |
| **`audit`** | checking the record after the fact |
| **`governance`** | the rules about who may do what |
| **`legal`** | contracts, regulation, counsel |
| **`permission`** | access control and who holds it |
| **`encryption`** | data protected in transit or at rest |
| `shield_lock` | a protected boundary |
| `shield_person` | protecting an individual's data |
| `fingerprint` | identity proven by something inherent |
| `vpn_key` | a credential or secret |
| `lock_open` | access deliberately granted |
| `password` | the credential is the subject |
| `security_update_good` | patched, current, no longer exposed |
| `balance` | a trade-off being weighed |
| `gavel` | a ruling, a decision with authority |

## Time

| Name | Reach for it when… |
|---|---|
| **`deadline`** | a date with consequences |
| **`duration`** | how long something takes |
| **`clock`** | time, generically |
| `schedule` | the same mark, for a recurring or planned time |
| **`calendar`** | a date, generically |
| `calendar_month` | a month-scale view |
| `event` | one thing at one time |
| `hourglass_top` | elapsed time is the cost |

## Talking to people

| Name | Reach for it when… |
|---|---|
| **`chat`** | a conversation with several people in it |
| **`message`** | a single message |
| **`email`** | email specifically (draws the built-in envelope) |
| **`phone`** | a call |
| **`video`** | a video call or recording |
| **`announcement`** | broadcasting outward |
| `podcasts` | audio content |
| `rss_feed` | a subscribable stream |
| `share` | passing something on |
| `link` | a reference to somewhere else |
| `translate` | languages, localisation |
| `record_voice_over` | speech as input |

## Places and industry

| Name | Reach for it when… |
|---|---|
| **`office`** | a company location |
| **`store`** | retail, a storefront, point of sale |
| `factory` | manufacturing or heavy process |
| `local_shipping` | physical delivery |
| `inventory_2` | stock, a warehouse, things counted |
| **`pin`** | a specific place on a map |
| `location_on` | the same mark, under the set's own name |
| `map` | geography is the frame |
| **`globe`** | the planet as a wireframe |
| **`world`** | global scope, drawn with continents |

## Documents

| Name | Reach for it when… |
|---|---|
| **`document`** | a file, as an object |
| `description` | a document with words in it |
| `article` | long-form writing |
| **`log`** | the same mark, for a running record |
| **`report`** | a produced summary |
| `summarize` | the act of condensing |
| `draft` | not finished, deliberately |
| `edit_note` | a document being changed |
| `note_add` | capturing something new |
| `folder_open` | contents rather than the container |
| `topic` | a category of documents |

## Interface verbs

| Name | Reach for it when… |
|---|---|
| **`eye`** | shown, watched, monitored |
| `visibility` / `visibility_off` | shown or hidden |
| **`gear`** | settings, as an object |
| `filter_alt` | narrowing a set |
| `sort` | ordering a set |
| `swap_horiz` | exchanging two things |
| `compare_arrows` | putting two things side by side |
| `open_in_new` | leaving for somewhere else |
| **`export`** | data leaving the system |
| **`import`** | data arriving in it |
| **`config`** | settings and knobs |
| `settings_suggest` | settings chosen for you |
| `toggle_on` / **`toggle`** | a binary switch |
| `touch_app` | a user acting directly |
| `ads_click` | conversion, the click that counted |
| `thumb_up` / `thumb_down` | feedback, sentiment |

## Sustainability and hardware

| Name | Reach for it when… |
|---|---|
| `eco` | environmental impact |
| `energy_savings_leaf` | efficiency framed as saving |
| `recycling` | a loop, reuse |
| `solar_power` | renewable generation |
| `smartphone` / `laptop_mac` / `devices` | the device is the subject |
| `qr_code_2` | a scannable handoff to a phone |
