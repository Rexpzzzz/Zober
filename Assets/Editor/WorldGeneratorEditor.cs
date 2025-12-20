#if UNITY_EDITOR
using UnityEngine;
using UnityEditor;
using System.IO;
using System;
using System.Linq;

public static class WorldGeneratorEditor
{
    [MenuItem("Tools/World Generator/Create Sample Biomes & Prefabs")]
    public static void CreateSampleBiomesAndPrefabs()
    {
        string root = "Assets/WorldAssets";
        if (!AssetDatabase.IsValidFolder(root)) AssetDatabase.CreateFolder("Assets", "WorldAssets");

        string prefabFolder = Path.Combine(root, "Prefabs").Replace("\\", "/");
        if (!AssetDatabase.IsValidFolder(prefabFolder)) AssetDatabase.CreateFolder(root, "Prefabs");

        string BiomeFolder = Path.Combine(root, "Biomes").Replace("\\", "/");
        if (!AssetDatabase.IsValidFolder(BiomeFolder)) AssetDatabase.CreateFolder(root, "Biomes");

        // Create biome-specific cube prefabs with distinct colors
        string[] biomeNames = new[] { "Air", "Earth", "Fire", "Spirit", "Water" };
        Color[] biomeColors = new[]
        {
            new Color(0.2f, 0.8f, 0.95f),    // Air (cyan)
            new Color(0.85f, 0.7f, 0.35f),   // Earth (tan)
            new Color(0.9f, 0.25f, 0.08f),   // Fire (red-orange)
            new Color(0.75f, 0.75f, 0.75f),  // Spirit (gray)
            new Color(0.05f, 0.2f, 0.7f)     // Water (blue)
        };

        for (int i = 0; i < biomeNames.Length; i++)
        {
            GameObject go = GameObject.CreatePrimitive(PrimitiveType.Cube);
            go.name = "BiomePrefab_" + biomeNames[i];
            var r = go.GetComponent<Renderer>();
            r.sharedMaterial = new Material(Shader.Find("Standard"));
            r.sharedMaterial.color = biomeColors[i];

            string prefabPath = prefabFolder + "/BiomePrefab_" + biomeNames[i] + ".prefab";
            PrefabUtility.SaveAsPrefabAsset(go, prefabPath);
            UnityEngine.Object.DestroyImmediate(go);
        }

        // Create Biome assets matching Shadowbane legend (Air, Earth, Fire, Spirit, Water)
        CreateBiomeAsset("Air", biomeColors[0], prefabFolder + "/BiomePrefab_Air.prefab", 0.66f, 1f);
        CreateBiomeAsset("Earth", biomeColors[1], prefabFolder + "/BiomePrefab_Earth.prefab", 0.25f, 0.6f);
        CreateBiomeAsset("Fire", biomeColors[2], prefabFolder + "/BiomePrefab_Fire.prefab", 0f, 0.35f);
        CreateBiomeAsset("Spirit", biomeColors[3], prefabFolder + "/BiomePrefab_Spirit.prefab", 0.6f, 0.9f);
        CreateBiomeAsset("Water", biomeColors[4], prefabFolder + "/BiomePrefab_Water.prefab", 0f, 0.18f);

        AssetDatabase.SaveAssets();
        AssetDatabase.Refresh();

        EditorUtility.DisplayDialog("World Generator", "Sample biomes and prefabs created at: " + root, "OK");
    }

    private static void CreateBiomeAsset(string name, Color color, string prefabPath, float min, float max)
    {
        // Create ScriptableObject by type name to avoid hard dependency on Biome type at compile time
        var so = ScriptableObject.CreateInstance("Biome") as ScriptableObject;
        if (so != null)
        {
            var sobj = new SerializedObject(so);
            var nameProp = sobj.FindProperty("biomeName"); if (nameProp != null) nameProp.stringValue = name;
            var colorProp = sobj.FindProperty("color"); if (colorProp != null) colorProp.colorValue = color;
            var prefabProp = sobj.FindProperty("prefab"); if (prefabProp != null) prefabProp.objectReferenceValue = AssetDatabase.LoadAssetAtPath<GameObject>(prefabPath);
            sobj.FindProperty("minHeight").floatValue = min;
            sobj.FindProperty("maxHeight").floatValue = max;
            sobj.ApplyModifiedProperties();

            string assetPath = $"Assets/WorldAssets/Biomes/{name}.asset";
            AssetDatabase.CreateAsset(so, assetPath);
        }
        else
        {
            Debug.LogWarning("Failed to create Biome asset: " + name);
        }
    }

    [MenuItem("Tools/World Generator/Generate Sample World")]
    public static void GenerateSampleWorld()
    {
        // Create or find generator object
        GameObject go = GameObject.Find("WorldGenerator");
        if (go == null)
        {
            go = new GameObject("WorldGenerator");
        }

        // Attempt to fix known DirectXSwapper DLL/plugin issues before generating
        try
        {
            var report = DirectXSwapperPluginFixer.TryFixDXSPlugins();
            if (!string.IsNullOrEmpty(report))
            {
                Debug.Log("DXS plugin fixer ran: " + report);
            }
        }
        catch (Exception ex)
        {
            Debug.LogWarning("DXS plugin fixer failed: " + ex.Message);
        }

        // Find runtime WorldGenerator type via reflection
        var wgType = AppDomain.CurrentDomain.GetAssemblies()
            .SelectMany(a => a.GetTypesSafe())
            .FirstOrDefault(t => t.Name == "WorldGenerator");

        UnityEngine.Object genComp = null;
        if (wgType != null)
        {
            genComp = go.GetComponent(wgType) as UnityEngine.Object;
            if (genComp == null)
                genComp = go.AddComponent(wgType) as UnityEngine.Object;
        }
        else
        {
            Debug.LogWarning("WorldGenerator runtime type not found. Created GameObject without component; generation will be skipped.");
        }

        // Load all biomes from Assets/WorldAssets/Biomes into the generator's serialized 'biomes' property
        string[] guids = AssetDatabase.FindAssets("t:ScriptableObject", new[] { "Assets/WorldAssets/Biomes" });
        if (genComp != null)
        {
            var genSO = new SerializedObject(genComp);
            var biomesProp = genSO.FindProperty("biomes");
            if (biomesProp != null)
            {
                biomesProp.ClearArray();
                foreach (var g in guids)
                {
                    string p = AssetDatabase.GUIDToAssetPath(g);
                    var obj = AssetDatabase.LoadAssetAtPath<UnityEngine.Object>(p);
                    if (obj != null)
                    {
                        biomesProp.arraySize++;
                        biomesProp.GetArrayElementAtIndex(biomesProp.arraySize - 1).objectReferenceValue = obj;
                    }
                }
            }

            // set generator params via serialized props
            var wProp = genSO.FindProperty("width"); if (wProp != null) wProp.intValue = 64;
            var hProp = genSO.FindProperty("height"); if (hProp != null) hProp.intValue = 64;
            var sProp = genSO.FindProperty("scale"); if (sProp != null) sProp.floatValue = 18f;
            var seedProp = genSO.FindProperty("seed"); if (seedProp != null) seedProp.intValue = UnityEngine.Random.Range(0, 999999);

            genSO.ApplyModifiedProperties();

            // invoke Generate() if available
            var mi = genComp.GetType().GetMethod("Generate");
            if (mi != null)
            {
                try { mi.Invoke(genComp, null); } catch (System.Exception ex) { Debug.LogError("Generate() invocation failed: " + ex.Message); }
            }
            else
            {
                Debug.LogWarning("WorldGenerator.Generate method not found.");
            }
        }
        else
        {
            Debug.LogWarning("Cannot assign biomes or run generation because runtime generator component is missing.");
        }

        Selection.activeGameObject = go;
        EditorUtility.DisplayDialog("World Generator", "Sample world generated in the current scene.", "OK");
    }
}
#endif