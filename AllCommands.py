import subprocess

def run_command(command):
    print(f"Exécution : {' '.join(command)}")
    subprocess.run(command, check=True)

def main():
    # Commandes en anglais
    print("=== Commandes en anglais ===")
    run_command(["python", "-m", "main", "download", "--loglevel", "info"])
    run_command(["python", "-m", "main", "updateExternalLinks", "--loglevel", "info"])
    run_command(["python", "-m", "main", "parse", "--loglevel", "info"])
    run_command(["python", "-m", "main", "verify", "--loglevel", "info"])
    print("Si des erreurs sont détectées, modifiez le fichier outputDataCorrections_en.json.")

    # Commandes en français
    print("\n=== Commandes en français ===")
    run_command(["python", "-m", "main", "download", "--language", "fr", "--loglevel", "info"])
    run_command(["python", "-m", "main", "updateExternalLinks", "--language", "fr", "--loglevel", "info"])
    run_command(["python", "-m", "main", "parse", "--language", "fr", "--loglevel", "info"])
    run_command(["python", "-m", "main", "verify", "--language", "fr", "--loglevel", "info"])
    print("Si des erreurs sont détectées, modifiez le fichier outputDataCorrections_fr.json.")

if __name__ == "__main__":
    main()
