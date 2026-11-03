//import { get } from "node:http";
import { useCallback, useRef, useState, createContext, useContext, type ReactNode } from "react";

//First we need to declare a global to make sure window know pyodide exists and checks how you can call it as well as use the return value
//we need to add a costume property to window which is called loadpyodide
// the promise will at some point give an object with the paramenters described inside, its a value that will be available asynchronously
declare global{
    interface Window{
        //declare a function called loadPyodide and add optional parameters for output, error and image?
        loadPyodide: (options? : {
            //handles normal output like a print func
            stdout?: (message: string) => void 
            //handels error output reporting a problem
            stderr?: (message: string) => void
        }) => Promise<{
            //this is a function that runs python async, the parameters is code and the options we have defined in loadpyodide, the ? makes them optional
            runPythonAsync: (code : string, options?: {globals?: unknown}) => Promise<unknown>
            //the globals value is another object that has the function property named get which returns a function
            globals: {get: (key: string) => () => unknown}
            FS: {
                writeFile: (path:string, data: Uint8Array) => void
                mkdir: (path: string) => void
            }
            loadPackage: (packages: string[]) => Promise<void> //lets us fetch matplotlib for the images
        }>
    }
}

//finds out what type of object pyodide gives you after it loads
type PyodideInterface = Awaited<ReturnType<Window['loadPyodide']>>
//stores it here - either a promise with pyodide or nothing yet
let pyodidePromise: Promise<PyodideInterface> | null = null

//storing the output and the error
let currentstdout: ((message: string) => void) | null = null
let currentstderr: ((message: string) => void) | null = null

//Checks if promise is made yet and if not then it calls the loadpyodide, uses a callback that passes the message to the current handler, if there is one
function getPy (){
    if (!pyodidePromise){
        pyodidePromise = window.loadPyodide({
            stdout: (message) => currentstdout?.(message),
            stderr: (message) => currentstderr?.(message)
        })
    }
    return pyodidePromise
}

//here we simplify the error message because the message is very long without
function simplifyError(message:string): string{
    const line = message.split('\n')
    const execIndex = line.findIndex((line) => line.includes('File "<exec>"'))
    if (execIndex === -1) return message
    return line.slice(execIndex).join('\n').trim()
}
// we make a box everyone can read of so the run botton doesnt need to be by the other components
type PyContextValue = ReturnType<typeof usePyInternal>
//the box itself, starts empty
const PyodideContext = createContext<PyContextValue | null>(null)

//all code before from usepy
function usePyInternal(){
//we add the 3 state variables that we have defined
    const [running, setRun] = useState(false) //tracks if the code is running
    const [output, setOut] = useState('') //is an empty string
    const [error, setErr] = useState<string | null>(null) //if its null there is no error, if its string it is the error
    const [image, setImg] = useState<string | null>(null) //to convert the file to an image

    const outRef = useRef('')

    const generatePlot = useCallback(async () => {
    setErr(null)
    //asks pyodide to download matplotlib from plotting library
    try{
        const pyodide = await getPy()
        await pyodide.loadPackage(['matplotlib'])
        //a python script that opens the file, read it as numbers, plots as linechart, save it as png image and converts the image into a string
        const base64Image = await pyodide.runPythonAsync(`
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io, base64
import csv

values = []

with open('/home/pyodide/EKG_data.txt', encoding='utf-8-sig') as f:
    reader = csv.reader(f, delimiter='\t')

    for row in reader:
        if len(row) >= 2:
            values.append(float(row[1]))

plt.figure(figsize=(12, 4))
plt.plot(values, linewidth=0.8)

plt.xlabel('Sample')
plt.ylabel('Voltage (mV)')
plt.title('EKG Data')
plt.grid(True, alpha=0.3)

plt.tight_layout()

buf = io.BytesIO()
plt.savefig(buf, format='png')
plt.close()
buf.seek(0)

base64.b64encode(buf.read()).decode('utf-8')`)
        setImg(base64Image as string)
    } catch (err: any) {
        setErr(err?.message ?? String(err))
    }
}, [])
//the variable image will be used in the plot script to show the image


    //recieves and uses the line of text in the output
    const useLine = useCallback((line: string) => {
        //if the line already exists it puts a newline in between
    outRef.current += (outRef.current ? '\n' : '') + line
    setOut(outRef.current)
  }, [])

  //this is the fuction being called by the UI when a user clicks the run button, its being recieved as a string
  const run = useCallback(
    async(code: string) => {
        outRef.current = ''
        setOut('') //resets everything when run
        setErr(null)
        setImg(null)
        setRun(true)
        try{
            const pyodide = await getPy()
            
            currentstdout = useLine
            currentstderr = useLine
            const namespace = pyodide.globals.get('dict')()
            await pyodide.runPythonAsync(code, {globals: namespace})

            if (code.includes('print(indhold)')){
                await generatePlot()

            }
            
        } catch (err) {
            const message = err instanceof Error ? err.message : String(err)
            setErr(simplifyError(message))// here it gets simplified
        } finally{
            setRun(false)
        }
    }, [useLine, generatePlot],
  )
  //for loading the file we have
async function loadFile(url: string, filename: string) {
    const pyodide = await getPy()
    const response = await fetch(url)
    if (!response.ok) {
        throw new Error(`Failed to load ${filename} from ${url} (status ${response.status})`)
    }
    const buffer = await response.arrayBuffer()
    pyodide.FS.writeFile(`/home/pyodide/${filename}`, new Uint8Array(buffer))
}

return{running, output, error, run, image, loadFile, generatePlot}

}

// this is the shared box: it holds ONE copy of the state above, and anything
// rendered inside it will see the same running/output/error/image values
export function PyodideProvider({ children }: { children: ReactNode }) {
    const value = usePyInternal()
    return (
        <PyodideContext.Provider value={value}>
            {children}
        </PyodideContext.Provider>
    )
}

// every component now reaches into the shared box instead of making its own
export function usePy(){
    const ctx = useContext(PyodideContext)
    if (!ctx) {
        throw new Error('usePy must be used inside a <PyodideProvider>')
    }
    return ctx
}