# Rezumatul analizei razelor comerciale Staer

> **Acesta este raportul în format ușor de citit.** Nu trebuie să descarci un
> PDF și nu ai nevoie de cunoștințe de programare.

## Concluzia pe scurt

- Analiza include **29.204 clienți** ai magazinelor Staer 7, Staer 9 și Staer 23.
- Au fost geocodați **28.992 clienți (99,27%)**.
- **212 clienți (0,73%)** au rămas marcați distinct drept
  „Negeocodat / nerutat”; nu au fost inventate sau extrapolate distanțe pentru ei.
- Intervalul rutier dominant pentru fiecare magazin și pentru total este
  **5–10 km**.
- Toate cele trei magazine au nivelul de încredere **„Acoperire solidă”**.

## Rezultate generale

| Indicator | Rezultat |
|---|---:|
| Clienți analizați | 29.204 |
| Adrese unice geocodate | 7.889 |
| Clienți geocodați | 28.992 |
| Acoperire geocodare | 99,27% |
| Clienți negeocodați / nerutați | 212 (0,73%) |
| Distanță rutieră medie | 8,80 km |
| Mediană (P50) | 7,24 km |
| P80 | 12,68 km |
| P90 | 15,91 km |
| P95 | 20,46 km |
| Interval dominant | 5–10 km |

**Cum se citește P80:** 80% dintre clienții cu rută calculată se află la cel
mult 12,68 km rutieri de magazinul asociat.

## Rezultate pe magazin

| Magazin | Clienți totali | Clienți geocodați | Acoperire | Medie rutieră | P50 | P80 | P90 | P95 | Interval dominant |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| Staer 7 | 6.617 | 6.444 | 97,39% | 10,35 km | 9,11 km | 13,55 km | 15,43 km | 20,01 km | 5–10 km |
| Staer 9 | 11.117 | 11.087 | 99,73% | 9,61 km | 7,72 km | 13,96 km | 17,86 km | 23,10 km | 5–10 km |
| Staer 23 | 11.470 | 11.461 | 99,92% | 7,14 km | 5,58 km | 10,29 km | 13,75 km | 17,83 km | 5–10 km |
| **Total** | **29.204** | **28.992** | **99,27%** | **8,80 km** | **7,24 km** | **12,68 km** | **15,91 km** | **20,46 km** | **5–10 km** |

### Staer 7

- Are 6.617 clienți, dintre care 6.444 geocodați.
- Acoperirea este de **97,39%**, iar 173 de clienți sunt negeocodați / nerutați.
- Raza P80 este de **13,55 km rutieri**.
- Principalele zone comerciale sunt Nord-Est (1.885 clienți), București
  neatribuit (1.459) și Nord (991).

### Staer 9

- Are 11.117 clienți, dintre care 11.087 geocodați.
- Acoperirea este de **99,73%**, iar 30 de clienți sunt negeocodați / nerutați.
- Raza P80 este de **13,96 km rutieri**.
- Principalele zone comerciale sunt Vest (3.736 clienți), Sud-Vest (2.027) și
  Nord (1.267).

### Staer 23

- Are 11.470 clienți, dintre care 11.461 geocodați.
- Acoperirea este de **99,92%**, iar 9 clienți sunt negeocodați / nerutați.
- Raza P80 este de **10,29 km rutieri**, cea mai compactă dintre cele trei.
- Principalele zone comerciale sunt Sud (5.800 clienți), Est (1.909) și
  București neatribuit (1.075).

## Distribuția tuturor clienților după distanța rutieră

Procentele de mai jos folosesc totalul complet de 29.204 clienți, inclusiv
clienții negeocodați / nerutați.

| Interval | Clienți | Procent din total |
|---|---:|---:|
| 0–3 km | 5.218 | 17,87% |
| 3–5 km | 4.656 | 15,94% |
| 5–10 km | 9.447 | 32,35% |
| 10–15 km | 6.222 | 21,31% |
| 15–25 km | 2.532 | 8,67% |
| Peste 25 km | 917 | 3,14% |
| Negeocodat / nerutat | 212 | 0,73% |
| **Total** | **29.204** | **100,00%** |

## Distribuția pe magazine

| Magazin | 0–3 km | 3–5 km | 5–10 km | 10–15 km | 15–25 km | Peste 25 km | Negeocodat / nerutat |
|---|---:|---:|---:|---:|---:|---:|---:|
| Staer 7 | 288 | 845 | 2.432 | 2.130 | 554 | 195 | 173 |
| Staer 9 | 1.618 | 1.908 | 3.449 | 2.303 | 1.365 | 444 | 30 |
| Staer 23 | 3.312 | 1.903 | 3.566 | 1.789 | 613 | 278 | 9 |

## Interpretare comercială

1. **Baza analizată este foarte bine acoperită.** La nivel total, lipsesc
   distanțele pentru numai 0,73% dintre clienți.
2. **Nucleul principal se află între 5 și 10 km.** Acesta este cel mai mare
   interval pentru toate cele trei magazine.
3. **Staer 23 are bazinul cel mai compact.** Valorile sale P50, P80, P90 și P95
   sunt cele mai mici dintre magazine.
4. **Staer 7 necesită cea mai multă prudență.** Are cea mai mică acoperire
   (97,39%) și cea mai mare distanță medie (10,35 km), deși rezultatul rămâne
   încadrat la „Acoperire solidă”.
5. **Rezultatele nu extrapolează cazurile lipsă.** Cei 212 clienți fără rezultat
   sunt păstrați în totaluri și raportați separat.

## Notă metodologică

- Distanțele din raport sunt distanțe **rutiere**, nu cercuri geografice în
  linie dreaptă.
- P50 reprezintă mediana; P80, P90 și P95 sunt pragurile sub care se găsesc
  80%, 90%, respectiv 95% dintre clienții cu rută calculată.
- Calculele sunt ponderate cu numărul de clienți.
- Etapa de analiză utilizează cache-urile locale și nu efectuează apeluri API.
- Totalurile sursei au fost reconciliate: Staer 7 = 6.617, Staer 9 = 11.117,
  Staer 23 = 11.470, total = 29.204.

