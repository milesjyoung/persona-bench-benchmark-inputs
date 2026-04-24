1. Clone the repo on the Ubuntu VM:
```bash
git clone https://github.com/milesjyoung/persona-bench-benchmark-inputs.git
cd persona-bench-benchmark-inputs
chmod +x scripts/run_openclaw_persona_pipeline.sh
```

2. Install and configure OpenClaw:
   - Follow [OpenClaw install](https://docs.openclaw.ai/install)
   - Complete the quickstart and provider/API key setup
   - You need a model provider and embeddings configured
   - Skip the extra onboarding beyond basic setup
   - If the TUI asks for a wake-up prompt, use:
```text
I am {persona_name}, you are OC the helpful and down to business personal agent.
```

3. Prepare the VM and host so long runs do not stop:
   - On the Mac host, keep the machine awake:
```bash
caffeinate -dimsu
```
   - On the Ubuntu VM, disable suspend:
```bash
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'
gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-battery-type 'nothing'
sudo systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target
```
   - Run the benchmark inside `tmux` on the VM:
```bash
sudo apt install -y tmux
tmux new -s bench
```

4. Run the full pipeline for one persona:
```bash
./scripts/run_openclaw_persona_pipeline.sh --persona alicia_gonzalez
```

What the script does:
   - Copies `generated/{persona}/{persona}_raw_app_logs.txt` into `~/.openclaw/workspace/memory/YYYY-MM-DD.md`
   - Runs `openclaw memory index --force`
   - Writes inference-mode `AGENTS.md`
   - Runs the benchmark question loop
   - Cleans the answers file
   - Writes eval-mode `AGENTS.md`
   - Runs the eval loop
   - Packages outputs into `generated/{persona}/{persona}_openclaw_results.tar.gz`
   - Prints the exact `scp` command to pull the archive back to the local machine

5. Useful pipeline options:
   - Resume a partial run:
```bash
./scripts/run_openclaw_persona_pipeline.sh --persona alicia_gonzalez --resume
```
   - Resume from a specific test case:
```bash
./scripts/run_openclaw_persona_pipeline.sh --persona alicia_gonzalez --resume --start-from TC-49
```
   - Skip question generation and run eval only:
```bash
./scripts/run_openclaw_persona_pipeline.sh --persona alicia_gonzalez --skip-questions --resume
```
   - Skip eval and only generate answers:
```bash
./scripts/run_openclaw_persona_pipeline.sh --persona alicia_gonzalez --skip-eval --resume
```

6. Detach and reattach `tmux`:
   - Detach and leave the run going:
```text
Ctrl+b d
```
   - Reattach later:
```bash
tmux attach -t bench
```

7. Output locations for each persona:
```text
generated/{persona}/{persona}_raw_app_logs.txt
generated/{persona}/{persona}_test_questions.json
generated/{persona}/{persona}_answers.json
generated/{persona}/{persona}_answers_clean.json
generated/{persona}/{persona}_eval.json
generated/{persona}/{persona}_openclaw_results.tar.gz
generated/{persona}/workspace_backups/
```

8. Best file transfer setup:
   - Install SSH on the VM once:
```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl enable --now ssh
hostname -I
```
   - Then pull the results archive from the local machine with `scp`:
```bash
scp user01@<VM_IP>:/home/user01/Desktop/persona-bench-benchmark-inputs/generated/alicia_gonzalez/alicia_gonzalez_openclaw_results.tar.gz ~/Downloads/
```
   - The pipeline script also prints the exact `scp` pull command for the persona you ran

9. Stop the overnight setup when done:
   - Stop the benchmark with `Ctrl+C` if it is still running
   - Exit or detach from `tmux`
   - Stop host sleep prevention by returning to the Mac terminal running `caffeinate` and pressing:
```text
Ctrl+C
```
