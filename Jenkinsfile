def PR_STATE="CREATED"
pipeline {
    agent {
        label 'linux'
    }
    environment {
        ENV="Staging"
        BITBUCKET_PROJECT="Hub"
        JIRA_PROJECT="VC"
        DEPLOY_REPO="Deployment"
    }

    parameters {
        string(name: 'RELEASE_BRANCH', defaultValue: '', description: 'Put release branch to run CI/CD')
        string(name: 'JIRA_LABEL', defaultValue: '', description: 'Put jira label to push change logs')
        string(name: 'REPO', defaultValue: 'pois', description: 'Repository to deploy (e.g., activity, pois)')
        string(name: 'PROJECTS', defaultValue: '', description: 'Comma-separated list of projects to deploy (leave empty to deploy all)')
        string(name: 'PROJECT_NAME', defaultValue: '', description: 'Project name for deployment (defaults to REPO if empty)')
        choice(name: 'BUILD_MODE', choices: ['CICD', 'CI'], defaultValue: 'CICD', description: 'Build mode: CI for build only, CICD for build and deploy')
    }
    
    stages {
        stage("Environment Check") {
            steps {
                sh 'echo "Checking build environment..."'
                sh 'python3 --version'
                sh 'which git'
                sh 'which yq'
                sh 'pwd'
                sh 'whoami'
            }
        }        
        stage("Clean up"){
            steps{
                echo "clean up workspace at path "
                sh "pwd"
                deleteDir()
            }
        }
        stage("Clone repos"){
            steps{
                // Clone Deployment repo
                sh "git clone ssh://git@bitbucket-ssh.vietmap.vn:7999/${BITBUCKET_PROJECT}/${DEPLOY_REPO}.git"
                
                // Clone repository to deploy
                sh "git clone ssh://git@bitbucket-ssh.vietmap.vn:7999/${BITBUCKET_PROJECT}/${params.REPO}.git"

                // Clone cd repo
                sh "git clone https://github.com/trongtqFX21166/vml_argocd.git"
            }
        }
        stage("Checkout branch"){
            steps{
                // Checkout the same branch in both repos
                dir("${DEPLOY_REPO}"){
                    sh "git checkout ${params.RELEASE_BRANCH}"
                }
                dir("${params.REPO}"){
                    sh "git checkout ${params.RELEASE_BRANCH}"
                }  
                dir("${params.REPO}"){
                    sh "git checkout ${params.RELEASE_BRANCH}"
                }              
            }
        }   
        stage("Build and Push Registry") {
            steps {
                script {
                    try {
                        dir("${WORKSPACE}/${DEPLOY_REPO}") {
                            // Ensure build.py exists and is executable
                            if (!fileExists('build.py')) {
                                error "build.py not found in expected location"
                            }
                            
                            // Process PROJECTS parameter to pass to build.py
                            def projectsParam = ""
                            if (params.PROJECTS?.trim()) {
                                projectsParam = params.PROJECTS.split(',').collect { it.trim() }.join(' ')
                            }
                            
                            sh """
                                chmod +x build.py
                                python3 build.py ${ENV} ${params.BUILD_MODE} ${params.REPO} ${projectsParam}
                            """
                        }
                    } catch (Exception e) {
                        error "Build failed: ${e.getMessage()}"
                    }
                }
            }
        }
        stage("Deploy to Kubernetes") {
            when {
                expression { params.BUILD_MODE == 'CICD' }
            }
            steps {
                script {
                    try {
                        dir("${WORKSPACE}/vml_argocd") {
                            echo "Starting Kubernetes deployment..."
                            
                            // Example ArgoCD deployment steps
                            sh """
                                echo "Updating ArgoCD application manifests..."
                                # Update image tags in ArgoCD manifests
                                # This would typically involve updating values.yaml or kustomization files
                                
                                echo "Committing changes to GitOps repository..."
                                #git config user.email "jenkins@vietmap.vn"
                                #git config user.name "Jenkins CI"
                                
                                # Example: Update image tags
                                # yq eval '.image.tag = "${BUILD_NUMBER}"' -i applications/${params.REPO}/values.yaml
                                
                                git add .
                                git commit -m "Deploy ${params.REPO} build ${BUILD_NUMBER} from branch ${params.RELEASE_BRANCH}" || echo "No changes to commit"
                                git push origin main
                                
                                echo "GitOps repository updated. ArgoCD will sync automatically."
                            """
                        }
                    } catch (Exception e) {
                        error "Deployment failed: ${e.getMessage()}"
                    }
                }
            }
        }
    }
    post {
        success {
            script {
                def mode = params.BUILD_MODE
                def statusMessage = mode == 'CICD' ? 'Build and Deploy Done' : 'Build Done'
                
                office365ConnectorSend webhookUrl: 'https://vietmapcorp.webhook.office.com/webhookb2/205670f3-463f-4ac3-85f8-f84b9f0da76e@fc2e159c-528b-4132-b3c0-f43226646ad7/JenkinsCI/74682a3b843b46529b662e5d4b85f65e/e1fe988a-0959-44ad-889d-44f6a1637286',
                    message: "${statusMessage}: ${env.JOB_NAME} [${env.BUILD_NUMBER}] - Repo: ${params.REPO}, Projects: ${params.PROJECTS ?: 'all'}, Mode: ${params.BUILD_MODE}",
                    status: 'Success',
                    color: '#28a745'
            }
        }        
        failure {
            script {
                def mode = params.BUILD_MODE
                def statusMessage = mode == 'CICD' ? 'Build and Deploy' : 'Build'
                
                office365ConnectorSend webhookUrl: 'https://vietmapcorp.webhook.office.com/webhookb2/205670f3-463f-4ac3-85f8-f84b9f0da76e@fc2e159c-528b-4132-b3c0-f43226646ad7/JenkinsCI/74682a3b843b46529b662e5d4b85f65e/e1fe988a-0959-44ad-889d-44f6a1637286',
                    message: "${env.JOB_NAME} - ${statusMessage} #${env.BUILD_NUMBER} failed for Repo: ${params.REPO}, Projects: ${params.PROJECTS ?: 'all'}, Mode: ${params.BUILD_MODE}. Check the Jenkins console output:\n ${env.BUILD_URL}console",
                    status: 'Fail',
                    color: '#dc3545'
            }
        }
    }    
}