#if UNITY_EDITOR
using System;
using System.IO;
using UnityEditor;
using UnityEngine;

public class DirectXSwapperPluginFixer
{
    // Finds d3d9.dll and d3d12.dll in Assets and sets plugin importer settings to disable Editor compatibility
    public static void DisableEditorCompatibilityForDXSPlugins()
    {
        try
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string[] names = new[] { "d3d9.dll", "d3d12.dll" };
            string resultsDir = Path.Combine(projectRoot, "tools", "directxswapper", "test_results");
            Directory.CreateDirectory(resultsDir);
            string outFile = Path.Combine(resultsDir, $"plugin_fix_{DateTime.Now:yyyyMMdd_HHmmss}.txt");

            using (var sw = new StreamWriter(outFile))
            {
                sw.WriteLine("DirectXSwapper Plugin Fix Results");
                sw.WriteLine("Project: " + projectRoot);

                foreach (var name in names)
                {
                    var files = Directory.GetFiles(Path.Combine(projectRoot, "Assets"), name, SearchOption.AllDirectories);
                    if (files.Length == 0)
                    {
                        sw.WriteLine($"No files found for {name}");
                        continue;
                    }

                    foreach (var f in files)
                    {
                        var relative = "Assets" + f.Replace(projectRoot, "").Replace('\\', '/');
                        try
                        {
                            var importer = AssetImporter.GetAtPath(relative) as PluginImporter;
                            if (importer == null)
                            {
                                sw.WriteLine($"Found {relative} but no PluginImporter available");
                                continue;
                            }

                            sw.WriteLine($"Processing {relative}");
                            importer.SetCompatibleWithAnyPlatform(false);
                            importer.SetCompatibleWithEditor(false);
                            importer.SetCompatibleWithPlatform(BuildTarget.StandaloneWindows, true);
                            importer.SetCompatibleWithPlatform(BuildTarget.StandaloneWindows64, true);
                            importer.SaveAndReimport();

                            sw.WriteLine(" - Actions: Set CompatibleWithEditor=false; StandaloneWindows=true; StandaloneWindows64=true");
                        }
                        catch (Exception ex)
                        {
                            sw.WriteLine($"Error processing {relative}: {ex.Message}");
                        }
                    }
                }

                sw.Flush();
            }

            Debug.Log($"DirectXSwapper plugin fix complete. Results: {outFile}");
        }
        catch (Exception ex)
        {
            Debug.LogError("Error in DisableEditorCompatibilityForDXSPlugins: " + ex);
            EditorApplication.Exit(1);
        }

        EditorApplication.Exit(0);
    }

    // Move found DLLs out of Assets into a timestamped backup so the Editor won't see duplicates
    public static void MoveDXSDLLsOutOfAssets()
    {
        try
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string[] names = new[] { "d3d9.dll", "d3d12.dll" };
            string backupRoot = Path.Combine(projectRoot, "tools", "directxswapper", "backups");
            Directory.CreateDirectory(backupRoot);
            string resultsDir = Path.Combine(projectRoot, "tools", "directxswapper", "test_results");
            Directory.CreateDirectory(resultsDir);
            string outFile = Path.Combine(resultsDir, $"move_dlls_{DateTime.Now:yyyyMMdd_HHmmss}.txt");

            using (var sw = new System.IO.StreamWriter(outFile))
            {
                sw.WriteLine("DirectXSwapper Move DLLs Results");
                sw.WriteLine("Project: " + projectRoot);

                foreach (var name in names)
                {
                    var files = Directory.GetFiles(Path.Combine(projectRoot, "Assets"), name, SearchOption.AllDirectories);
                    if (files.Length == 0)
                    {
                        sw.WriteLine($"No files found for {name}");
                        continue;
                    }

                    foreach (var f in files)
                    {
                        var rel = "Assets" + f.Replace(projectRoot, "").Replace('\\', '/');
                        try
                        {
                            string folderName = Path.GetFileName(Path.GetDirectoryName(f)).Replace(' ', '_');
                            string backupFolder = Path.Combine(backupRoot, folderName + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss"));
                            Directory.CreateDirectory(backupFolder);
                            string dst = Path.Combine(backupFolder, Path.GetFileName(f));
                            File.Move(f, dst);
                            sw.WriteLine($"Moved {rel} -> {dst}");
                        }
                        catch (Exception ex)
                        {
                            sw.WriteLine($"Failed to move {rel}: {ex.Message}");
                        }
                    }
                }

                sw.Flush();
            }

            // Refresh AssetDatabase so Unity knows about moved files
            AssetDatabase.Refresh();
            Debug.Log($"MoveDLLs complete. Results: {outFile}");
        }
        catch (Exception ex)
        {
            Debug.LogError("Error in MoveDXSDLLsOutOfAssets: " + ex);
            EditorApplication.Exit(1);
        }

        EditorApplication.Exit(0);
    }

    // Non-exiting wrapper for use in-editor: attempts to set importer flags or move DLLs if importer is missing.
    public static string TryFixDXSPlugins(bool moveMissingDlls = true)
    {
        try
        {
            string projectRoot = Path.GetFullPath(Path.Combine(Application.dataPath, ".."));
            string[] names = new[] { "d3d9.dll", "d3d12.dll" };
            string resultsDir = Path.Combine(projectRoot, "tools", "directxswapper", "test_results");
            Directory.CreateDirectory(resultsDir);
            string outFile = Path.Combine(resultsDir, $"plugin_fix_brief_{DateTime.Now:yyyyMMdd_HHmmss}.txt");

            using (var sw = new StreamWriter(outFile))
            {
                sw.WriteLine("DirectXSwapper TryFixDXSPlugins Results");
                sw.WriteLine("Project: " + projectRoot);

                foreach (var name in names)
                {
                    var files = Directory.GetFiles(Path.Combine(projectRoot, "Assets"), name, SearchOption.AllDirectories);
                    if (files.Length == 0)
                    {
                        sw.WriteLine($"No files found for {name}");
                        continue;
                    }

                    foreach (var f in files)
                    {
                        var relative = "Assets" + f.Replace(projectRoot, "").Replace('\\', '/');
                        try
                        {
                            var importer = AssetImporter.GetAtPath(relative) as PluginImporter;
                            if (importer != null)
                            {
                                sw.WriteLine($"Processing {relative}");
                                importer.SetCompatibleWithAnyPlatform(false);
                                importer.SetCompatibleWithEditor(false);
                                importer.SetCompatibleWithPlatform(BuildTarget.StandaloneWindows, true);
                                importer.SetCompatibleWithPlatform(BuildTarget.StandaloneWindows64, true);
                                importer.SaveAndReimport();
                                sw.WriteLine(" - Actions: Set CompatibleWithEditor=false; StandaloneWindows=true; StandaloneWindows64=true");
                                continue;
                            }

                            // if no importer and moveMissingDlls requested, move file out of Assets
                            if (moveMissingDlls)
                            {
                                string backupRoot = Path.Combine(projectRoot, "tools", "directxswapper", "backups");
                                Directory.CreateDirectory(backupRoot);
                                string folderName = Path.GetFileName(Path.GetDirectoryName(f)).Replace(' ', '_');
                                string backupFolder = Path.Combine(backupRoot, folderName + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss"));
                                Directory.CreateDirectory(backupFolder);
                                string dst = Path.Combine(backupFolder, Path.GetFileName(f));
                                File.Move(f, dst);
                                sw.WriteLine($"Moved {relative} -> {dst}");
                            }
                            else
                            {
                                sw.WriteLine($"Found {relative} but no PluginImporter available");
                            }
                        }
                        catch (Exception ex)
                        {
                            sw.WriteLine($"Error processing {relative}: {ex.Message}");
                        }
                    }
                }

                sw.Flush();
            }

            AssetDatabase.Refresh();
            Debug.Log($"TryFixDXSPlugins complete. Results: {outFile}");
            return outFile;
        }
        catch (Exception ex)
        {
            Debug.LogError("TryFixDXSPlugins failed: " + ex);
            return null;
        }
    }
}
#endif