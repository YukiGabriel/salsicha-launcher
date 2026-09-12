import javax.swing.*;
import java.awt.*;
import java.awt.event.WindowAdapter;
import java.awt.event.WindowEvent;
import java.io.*;
import java.net.URISyntaxException;
import java.nio.file.*;
import java.util.ArrayList;
import java.util.List;

/**
 * Salsicha Launcher — lançador .jar multiplataforma.
 * Não reimplementa o launcher: localiza o projeto Python ao lado do .jar
 * e executa main.py, exibindo logs e erros amigáveis em qualquer SO.
 *
 * Build sem Maven/Gradle:
 *   javac --release 17 -d classes java/SalsichaLauncher.java
 *   jar --create --file dist/SalsichaLauncher.jar --main-class SalsichaLauncher -C classes .
 */
public class SalsichaLauncher {
    private static JFrame frame;
    private static JTextArea logArea;
    private static JLabel statusLabel;
    private static JButton launchButton;
    private static Process gameProcess;

    public static void main(String[] args) {
        SwingUtilities.invokeLater(SalsichaLauncher::createUI);
    }

    private static void createUI() {
        frame = new JFrame("Salsicha Launcher 🌭");
        frame.setDefaultCloseOperation(JFrame.DO_NOTHING_ON_CLOSE);
        frame.setSize(620, 440);
        frame.setLocationRelativeTo(null);
        frame.setLayout(new BorderLayout(8, 8));

        JPanel top = new JPanel(new BorderLayout(8, 8));
        top.setBorder(BorderFactory.createEmptyBorder(12, 12, 0, 12));
        JLabel title = new JLabel("🌭 Salsicha Launcher");
        title.setFont(title.getFont().deriveFont(Font.BOLD, 18f));
        top.add(title, BorderLayout.WEST);
        statusLabel = new JLabel("procurando projeto...");
        top.add(statusLabel, BorderLayout.EAST);
        frame.add(top, BorderLayout.NORTH);

        logArea = new JTextArea();
        logArea.setEditable(false);
        logArea.setFont(new Font(Font.MONOSPACED, Font.PLAIN, 12));
        JScrollPane scroll = new JScrollPane(logArea);
        scroll.setBorder(BorderFactory.createEmptyBorder(8, 12, 0, 12));
        frame.add(scroll, BorderLayout.CENTER);

        JPanel bottom = new JPanel(new FlowLayout(FlowLayout.RIGHT));
        bottom.setBorder(BorderFactory.createEmptyBorder(0, 12, 12, 12));
        launchButton = new JButton("▶ Abrir Launcher");
        launchButton.addActionListener(e -> launchAsync());
        JButton closeBtn = new JButton("Fechar");
        closeBtn.addActionListener(e -> closeAll());
        bottom.add(launchButton);
        bottom.add(closeBtn);
        frame.add(bottom, BorderLayout.SOUTH);

        frame.addWindowListener(new WindowAdapter() {
            @Override public void windowClosing(WindowEvent e) { closeAll(); }
        });

        frame.setVisible(true);
        log("Salsicha Launcher (.jar multiplataforma) iniciado.");
        log("Java: " + System.getProperty("java.version") + " — " + System.getProperty("os.name"));
        launchAsync();
    }

    private static void launchAsync() {
        launchButton.setEnabled(false);
        statusLabel.setText("iniciando...");
        new Thread(() -> {
            try {
                Path projectRoot = findProjectRoot();
                if (projectRoot == null) {
                    throw new IllegalStateException(
                        "main.py não encontrado ao lado do .jar.\n" +
                        "Coloque SalsichaLauncher.jar na pasta do projeto\n" +
                        "(onde fica main.py) ou em dist/ dentro dela.");
                }
                log("Projeto: " + projectRoot);
                String python = findPython(projectRoot);
                if (python == null) {
                    throw new IllegalStateException(friendlyPythonHelp());
                }
                log("Python: " + python);
                startPython(projectRoot, python);
            } catch (Exception ex) {
                SwingUtilities.invokeLater(() -> {
                    statusLabel.setText("erro");
                    log("ERRO: " + ex.getMessage());
                    JOptionPane.showMessageDialog(frame, ex.getMessage(),
                        "Salsicha Launcher", JOptionPane.ERROR_MESSAGE);
                    launchButton.setEnabled(true);
                });
            }
        }, "salsicha-launch").start();
    }

    private static Path findProjectRoot() {
        List<Path> candidates = new ArrayList<>();
        // 1. Diretório do .jar
        try {
            Path jarDir = Paths.get(
                SalsichaLauncher.class.getProtectionDomain()
                    .getCodeSource().getLocation().toURI()).getParent();
            if (jarDir != null) {
                candidates.add(jarDir);
                if (jarDir.getFileName() != null
                        && jarDir.getFileName().toString().equalsIgnoreCase("dist")
                        && jarDir.getParent() != null) {
                    candidates.add(jarDir.getParent());
                }
            }
        } catch (URISyntaxException | SecurityException ignored) {}
        // 2. Diretório atual
        candidates.add(Paths.get(System.getProperty("user.dir")));
        // 3. Local padrão do projeto
        candidates.add(Paths.get(System.getProperty("user.home"), "Projects", "salsicha-launcher"));

        for (Path base : candidates) {
            if (base != null && Files.isRegularFile(base.resolve("main.py"))) {
                return base.toAbsolutePath().normalize();
            }
        }
        return null;
    }

    private static String findPython(Path root) {
        boolean win = System.getProperty("os.name").toLowerCase().contains("win");
        List<Path> local = List.of(
            root.resolve(".venv").resolve(win ? "Scripts/python.exe" : "bin/python"),
            root.resolve(".venv").resolve(win ? "Scripts/python3.exe" : "bin/python3")
        );
        for (Path p : local) {
            if (Files.isExecutable(p) || Files.isRegularFile(p)) return p.toString();
        }
        String[] cmds = win
            ? new String[]{"python", "python3", "py"}
            : new String[]{"python3", "python"};
        for (String c : cmds) {
            try {
                List<String> probe = c.equals("py")
                    ? List.of("py", "-3", "--version")
                    : List.of(c, "--version");
                Process pr = new ProcessBuilder(probe).redirectErrorStream(true).start();
                if (pr.waitFor() == 0) return c;
            } catch (Exception ignored) {}
        }
        return null;
    }

    private static void startPython(Path root, String python) throws IOException {
        List<String> cmd = new ArrayList<>();
        cmd.add(python);
        // "uv run" seria ideal em dev, mas aqui vamos direto para funcionar em qualquer PC.
        cmd.add("main.py");
        ProcessBuilder pb = new ProcessBuilder(cmd);
        pb.directory(root.toFile());
        pb.redirectErrorStream(true);
        log("$ " + String.join(" ", cmd));
        gameProcess = pb.start();
        SwingUtilities.invokeLater(() -> {
            statusLabel.setText("rodando ✓");
            log("Launcher aberto. Esta janela mostra os logs — pode minimizar.");
            launchButton.setEnabled(true);
            launchButton.setText("↻ Reiniciar");
        });
        try (BufferedReader r = new BufferedReader(
                new InputStreamReader(gameProcess.getInputStream()))) {
            String line;
            while ((line = r.readLine()) != null) {
                final String l = line;
                SwingUtilities.invokeLater(() -> {
                    log(l);
                    if (l.toLowerCase().contains("error")
                            || l.toLowerCase().contains("traceback")) {
                        statusLabel.setText("verifique o log ⚠");
                    }
                });
            }
        }
        try {
            int code = gameProcess.waitFor();
            SwingUtilities.invokeLater(() -> {
                statusLabel.setText("encerrado (" + code + ")");
                log("Processo Python terminou com código " + code + ".");
            });
        } catch (InterruptedException ie) {
            Thread.currentThread().interrupt();
        }
    }

    private static String friendlyPythonHelp() {
        String os = System.getProperty("os.name");
        return "Python 3.10+ não encontrado (" + os + ").\n\n" +
               "• Windows: instale em python.org (marque ADD TO PATH)\n" +
               "• Linux: sudo pacman -S python python-pyside6  (ou apt/dnf equivalente)\n" +
               "• macOS: brew install python\n\n" +
               "Depois clique em Reiniciar.";
    }

    private static void log(String msg) {
        if (logArea == null) { System.out.println(msg); return; }
        logArea.append(msg + "\n");
        logArea.setCaretPosition(logArea.getDocument().getLength());
        System.out.println(msg);
    }

    private static void closeAll() {
        if (gameProcess != null && gameProcess.isAlive()) {
            int opt = JOptionPane.showConfirmDialog(frame,
                "Encerrar o launcher também?", "Sair",
                JOptionPane.YES_NO_OPTION);
            if (opt == JOptionPane.YES_OPTION) gameProcess.destroy();
            else return;
        }
        frame.dispose();
        System.exit(0);
    }
}
