using System;
using System.Diagnostics;
using System.IO;
using System.Text;

internal static class StartLauncher
{
    private static int Main(string[] args)
    {
        var pauseBeforeClose = true;
        var forwardedArgs = new StringBuilder();

        foreach (var arg in args)
        {
            if (string.Equals(arg, "--no-pause", StringComparison.OrdinalIgnoreCase))
            {
                pauseBeforeClose = false;
                continue;
            }

            forwardedArgs.Append(' ').Append(QuoteArgument(arg));
        }

        var projectRoot = AppDomain.CurrentDomain.BaseDirectory;
        var startScript = Path.Combine(projectRoot, "robustness_experiments", "Start.ps1");
        var exitCode = 1;

        try
        {
            if (!File.Exists(startScript))
            {
                throw new FileNotFoundException("Start.ps1 was not found in robustness_experiments.", startScript);
            }

            Console.Title = "Almond startup";

            var startInfo = new ProcessStartInfo
            {
                FileName = Path.Combine(Environment.SystemDirectory, "WindowsPowerShell\\v1.0\\powershell.exe"),
                Arguments = "-NoLogo -NoProfile -ExecutionPolicy Bypass -File " + QuoteArgument(startScript) + forwardedArgs,
                WorkingDirectory = projectRoot,
                UseShellExecute = false,
            };

            using (var process = Process.Start(startInfo))
            {
                if (process == null)
                {
                    throw new InvalidOperationException("Could not start PowerShell.");
                }

                process.WaitForExit();
                exitCode = process.ExitCode;
            }
        }
        catch (Exception error)
        {
            Console.Error.WriteLine();
            Console.Error.WriteLine("Almond could not start: {0}", error.Message);
        }

        Console.WriteLine();
        Console.WriteLine("Almond finished with exit code {0}.", exitCode);
        if (pauseBeforeClose)
        {
            Console.Write("Press any key to close this window...");
            Console.ReadKey(intercept: true);
            Console.WriteLine();
        }

        return exitCode;
    }

    private static string QuoteArgument(string value)
    {
        var quoted = new StringBuilder("\"");
        var backslashCount = 0;

        foreach (var character in value)
        {
            if (character == '\\')
            {
                backslashCount++;
                continue;
            }

            if (character == '"')
            {
                quoted.Append('\\', backslashCount * 2 + 1);
                quoted.Append(character);
                backslashCount = 0;
                continue;
            }

            quoted.Append('\\', backslashCount);
            quoted.Append(character);
            backslashCount = 0;
        }

        quoted.Append('\\', backslashCount * 2);
        quoted.Append('"');
        return quoted.ToString();
    }
}
