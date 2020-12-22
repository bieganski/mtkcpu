# CPU

* branching - psuje początek pipeline'u

prosty b. pred: jesli widzi skok do tylu to mowi ze skoczymy, else nie (bo pętle)

dynamiczny - 1 bit stanu na instr
dla kazdej instr przewidujemy czy skakala czy nie
jesli skoczyla wczesniej to przewiduje ze skoczy
jeszcze lepszy: 2 bity stanu, dodatkowy bit:
zmieniamy zdanie jesli dwa razy sie pomylimy

ret - oddzielny branch predictor - wejscie: lista retów

Offtop ciekawostka na temat predykcji returnów: dzięki temu, że ret ma osobny predyktor, w kernelu często robi się jumpy przez call/ret z podmienionym adresem reta, zamiast przez normalne instrukcje skoku, żeby łatać spectre. Tzw. retpoline jakby ktoś chciał googlować.

inny: dla kazdego n jakis bit (nauczenie sie historii skokow)
mozna napisac beznajdziejny bmark zalezny od branch predictora

out of order - problemy
* load moze rzucic wyjatek jak zly adres
trzeba umieć cofnąć stan programu
retired - stan rejestrow w momencie ostatniej w pelni wykonanej instrukcji
renaming - przełączanie banków rejestrow
* dla kazdego rejestru mozna trzymac bit dirty i czekac az load sie skonczy i ją odpali

speculative (spekulacja):
wykonywanie instrukcji "na wyrost"
* wymaga cofania na 1000%
!!!spectre!!! - tu był problem
ucząc predictory różnych rzeczy to zostaje w cache
i mozna timing attack

superscalar: 
n instr/cycle
* super decoder, n=np.8 instr na raz, czyta i szuka zaleznosci miedzy nimi


testowanie:
* weryfikacja formalna (właściwości)
asserty // system verilog assertions - kompiluje sie do zwyklej logiki i komorki ktora reprezentuje asserta
sat solver ze stanem
