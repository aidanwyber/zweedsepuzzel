
read -p "Seed: " SEED
python3 -m generator.template_generator --attempts 2000 --keep 10 --seed "$SEED" --verbose
python3 -m generator.generate --template "random-10x17-$SEED"
python3 generate.generate