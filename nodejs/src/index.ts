import { SSMClient, GetParametersByPathCommand, paginateGetParametersByPath } from "@aws-sdk/client-ssm";
// import console;

const createPath = (obj, path, value = null) => {
    path = typeof path === 'string' ? path.split('/') : path;
    let current = obj;
    while (path.length > 1) {
        const [head, ...tail] = path;
        path = tail;
        if (current[head] === undefined) {
            current[head] = {};
        }
        current = current[head];
    }
    current[path[0]] = value;
    return obj;
};

async function getSSMPaginator(root_path: string) {
    const client = new SSMClient({ region: "eu-west-2" });
    
    try {
        let params = {
            Path: root_path,
            WithDecryption: true,
            Recursive: true
        };
        let paginator = paginateGetParametersByPath({ client: client }, params)
        return paginator
        
    } catch (error) {
        console.log(error)
    }
}

function getSSMRootPath(environment, prefix, appname=undefined) {
    if (prefix == "/appconfig") {
        return prefix + "/" + appname + "/" + environment;
    } else {
        if (appname) {
            return prefix + "/" + environment + "/" + appname
        }
        return prefix + "/" + environment
    }
}

export function getSSMPath(environment, prefix, appname, key) {
    return getSSMRootPath(environment, prefix, appname) + "/" + key
}

export async function getSSMParameters(environment, prefix=undefined, appname="") {
    let parameters = {}
    const root_path = getSSMRootPath(environment, prefix, appname);
    console.log(root_path)
    let paginator = await getSSMPaginator(root_path)
    for await (let page of paginator) {
        for (let parameter_i in page.Parameters) {
            createPath(parameters, page.Parameters[parameter_i]["Name"].replace(root_path, "").substr(1), page.Parameters[parameter_i]["Value"])
        }
    }
    return parameters
}

