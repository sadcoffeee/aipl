//import { get } from "node:http";
import { useCallback, useRef, useState } from "react";

//First we need to declare a global to make sure window know pyodide exists and checks how you can call it as well as use the return value
//we need to add a costume property to window which is called loadpyodide
// the promise will at some point give an object with the paramenters described inside, its a value that will be available asynchronously
declare global{
    interface Window{
        //declare a function called loadPyodide and add optional parameters for output, error and image?
        loadPyodide: (options?: {
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
            }
            loadPackage: (names: string | string[]) => Promise<void>
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
// a function we can export in other files
export function usePy(){
//we add the 3 state variables that we have defined
    const [running, setRun] = useState(false) //tracks if the code is running
    const [output, setOut] = useState('') //is an empty string
    const [error, setErr] = useState<string | null>(null) //if its null there is no error, if its string it is the error
    const [image, setImg] = useState<string | null>(null) //to convert the file to an image

    const outRef = useRef('')

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
            await pyodide.loadPackage('matplotlib') //is used to make the image
            currentstdout = useLine
            currentstderr = useLine
            const namespace = pyodide.globals.get('dict')()
            await pyodide.runPythonAsync(code, {globals: namespace})

        } catch (err) {
            const message = err instanceof Error ? err.message : String(err)
            setErr(simplifyError(message))// here it gets simplified
        } finally{
            setRun(false)
        }
    }, [useLine],
  )
  //for loading the file we have
async function loadFile(url: string, filename: string) {
    const pyodide = await getPy()
    const response = await fetch(url) // downloads file from folder
    const buffer = await response.arrayBuffer() //turns response into raw bits
    pyodide.FS.writeFile(filename, new Uint8Array(buffer)) //writes into pyodides filesystem under a filename
}

return{running, output, error, run, image,loadFile}



}
